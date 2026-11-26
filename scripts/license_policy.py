#!/usr/bin/env python3
"""Dependency licence policy checker for REX (issue #38).

`license_policy.py check` validates the single source of truth for allowed
dependency licences, `.github/dependency-review-config.yml` (read by
actions/dependency-review-action v5), against the policy in
`docs/security/dependency-licenses.md`:

  LP-CONFIG       config exists and parses the way the action parses it (no duplicate
                  keys; lists or comma-separated strings only), allow-licenses is
                  non-empty without duplicates, and nothing switches enforcement off
                  (license-check: false, warn-only: true)
  LP-SPDX         every allowed id is a canonical, non-deprecated SPDX licence id
  LP-DENIED       every allowed id is in the owner-approved set (APPROVED below)
  LP-DENY-OPTION  the deprecated deny-licenses option is not used
  LP-EXCEPTION    each allow-dependencies-licenses entry is a valid purl, documented
                  in the policy with a reason and an issue reference
  LP-DOC          the policy doc exists, and its allowlist and exceptions equal the config's

Output: one '<path>: <CODE> <detail>' line per finding; exit 1 if any, else 0.
Run: uv run --no-project --with pyyaml==6.0.4 --with license-expression==30.4.4 \
       --with packageurl-python==0.17.6 --with markdown-it-py==4.3.0 \
       python scripts/license_policy.py check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from license_expression import get_license_index
from markdown_it import MarkdownIt
from packageurl import PackageURL

CONFIG = ".github/dependency-review-config.yml"
DOC = "docs/security/dependency-licenses.md"

# The owner-approved allowlist (2026-11-27). Changing it needs an owner-approved PR
# that edits this set, the config and the policy doc together.
APPROVED = frozenset({
    "MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0",
    "0BSD", "CC0-1.0", "Unlicense", "Zlib", "MPL-2.0",
})

ISSUE = re.compile(
    r"^(?:#\d+"
    r"|[\w.-]+/[\w.-]+#\d+"
    r"|https://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+"
    r"|\[[^\]]+\]\(https://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+\))$"
)
MD = MarkdownIt("commonmark").enable("table")


class ConfigError(Exception):
    pass


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys, like the `yaml` package the action uses."""


def _no_duplicates(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ConfigError(f"duplicate key {key!r}")
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def as_list(value: object, key: str) -> list[str]:
    """Normalise like the action: a list of strings, or one comma-separated string."""
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return [v.strip() for v in value]
    raise ConfigError(f"{key} must be a list of strings or a comma-separated string")


def canonical_spdx_ids() -> set[str]:
    return {entry["spdx_license_key"] for entry in get_license_index()
            if entry.get("spdx_license_key") and not entry.get("is_exception")
            and not entry["spdx_license_key"].startswith("LicenseRef-")}


def doc_tables(text: str) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """(allowed ids, {purl: (reason, issue)}) from the tables under '## Allowed…' and '## Exceptions'."""
    allowed: list[str] = []
    exceptions: dict[str, tuple[str, str]] = {}
    section, in_body, row, cells = "", False, False, []
    for tok in MD.parse(text):
        if tok.type == "heading_open" and tok.tag == "h2":
            section = "heading"
        elif tok.type == "inline" and section == "heading":
            section = tok.content.strip().lower()
        elif tok.type == "tbody_open":
            in_body = True
        elif tok.type == "tbody_close":
            in_body = False
        elif tok.type == "tr_open" and in_body:
            row, cells = True, []
        elif tok.type == "inline" and row:
            cells.append(tok.content.strip())
        elif tok.type == "tr_close" and row:
            row = False
            if not cells or not (cells[0].startswith("`") and cells[0].endswith("`")):
                continue
            key = cells[0].strip("`").strip()
            if section.startswith("allowed"):
                allowed.append(key)
            elif section.startswith("exceptions"):
                exceptions[key] = (cells[1] if len(cells) > 1 else "", cells[2] if len(cells) > 2 else "")
    return allowed, exceptions


def valid_purl(text: str) -> bool:
    try:
        purl = PackageURL.from_string(text)
    except ValueError:
        return False
    return bool(purl.type and purl.name)


def check(root: Path) -> int:
    findings: list[str] = []

    def report(path: str, code: str, detail: str) -> None:
        findings.append(f"{path}: {code} {detail}")

    allow: list[str] = []
    exceptions: list[str] = []
    config_path = root / CONFIG
    if not config_path.is_file():
        report(CONFIG, "LP-CONFIG", "missing")
    else:
        try:
            data = yaml.load(config_path.read_text(encoding="utf-8"), Loader=StrictLoader)  # noqa: S506 - SafeLoader subclass
            if not isinstance(data, dict):
                raise ConfigError("not a YAML mapping")
            allow = as_list(data.get("allow-licenses"), "allow-licenses")
            exceptions = as_list(data.get("allow-dependencies-licenses"), "allow-dependencies-licenses")
            if not allow:
                report(CONFIG, "LP-CONFIG", "allow-licenses is empty")
            for lic in sorted({lic for lic in allow if allow.count(lic) > 1}):
                report(CONFIG, "LP-CONFIG", f"duplicate allow-licenses entry {lic}")
            if data.get("license-check") is False:
                report(CONFIG, "LP-CONFIG", "license-check: false disables the licence policy")
            if data.get("warn-only") is True:
                report(CONFIG, "LP-CONFIG", "warn-only: true turns every failure into a warning")
            if "deny-licenses" in data:
                report(CONFIG, "LP-DENY-OPTION", "deny-licenses is deprecated; use allow-licenses only")
        except (yaml.YAMLError, ConfigError) as exc:
            report(CONFIG, "LP-CONFIG", f"invalid: {str(exc).splitlines()[0]}")

    spdx = canonical_spdx_ids()
    for lic in allow:
        if lic not in spdx:
            report(CONFIG, "LP-SPDX", f"{lic!r} is not a canonical SPDX licence id")
        if lic not in APPROVED:
            report(CONFIG, "LP-DENIED", f"{lic} is not in the owner-approved allowlist")

    doc_path = root / DOC
    doc_allowed: list[str] = []
    doc_exceptions: dict[str, tuple[str, str]] = {}
    if not doc_path.is_file():
        report(DOC, "LP-DOC", "missing policy document")
    else:
        doc_allowed, doc_exceptions = doc_tables(doc_path.read_text(encoding="utf-8"))
        if sorted(doc_allowed) != sorted(allow):
            report(DOC, "LP-DOC", f"allowlist differs from {CONFIG}: "
                   f"only in doc {sorted(set(doc_allowed) - set(allow))}, "
                   f"only in config {sorted(set(allow) - set(doc_allowed))}")
        for purl in sorted(set(doc_exceptions) - set(exceptions)):
            report(DOC, "LP-DOC", f"exception {purl} is documented but not in {CONFIG}")

    for purl in exceptions:
        if not valid_purl(purl):
            report(CONFIG, "LP-EXCEPTION", f"{purl!r} is not a valid package URL")
            continue
        if purl not in doc_exceptions:
            report(DOC, "LP-EXCEPTION", f"{purl} is not documented")
            continue
        reason, issue = doc_exceptions[purl]
        if not reason or ISSUE.match(reason) or not ISSUE.match(issue):
            report(DOC, "LP-EXCEPTION", f"{purl} needs a reason and an issue reference")

    if findings:
        print("\n".join(findings))
        return 1
    print(f"licence policy OK: {len(allow)} allowed licences, {len(exceptions)} exceptions")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REX dependency licence policy")
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check", help="validate the licence policy config and doc")
    check_cmd.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    return check(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())
