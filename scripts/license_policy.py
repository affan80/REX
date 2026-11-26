#!/usr/bin/env python3
"""Dependency licence policy checker for REX (issue #38).

`license_policy.py check` validates the single source of truth for allowed
dependency licences, `.github/dependency-review-config.yml`, against the policy
in `docs/security/dependency-licenses.md`:

  LP-CONFIG       config exists, parses, and has a non-empty allow-licenses list
  LP-SPDX         every allowed id is a canonical, non-deprecated SPDX licence id
  LP-DENIED       no copyleft or source-available licence (GPL, AGPL, LGPL, SSPL, BUSL)
  LP-DENY-OPTION  the deprecated deny-licenses option is not used
  LP-EXCEPTION    each allow-dependencies-licenses entry is a valid purl, documented
                  in the policy with a reason and an issue reference
  LP-DOC          the policy doc exists and its allowlist equals the config

Output: one '<path>: <CODE> <detail>' line per finding; exit 1 if any, else 0.
Run: uv run --no-project --with pyyaml==6.0.4 --with license-expression==30.4.4 \
       --with packageurl-python==0.17.6 python scripts/license_policy.py check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from license_expression import get_license_index
from packageurl import PackageURL

CONFIG = ".github/dependency-review-config.yml"
DOC = "docs/security/dependency-licenses.md"
DENIED = re.compile(r"^(A?GPL|LGPL|SSPL|BUSL)-", re.IGNORECASE)
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|(.*)$")
ISSUE = re.compile(r"^(#\d+|https://github\.com/[^/\s]+/[^/\s]+/issues/\d+)$")


def canonical_spdx_ids() -> set[str]:
    return {entry["spdx_license_key"] for entry in get_license_index()
            if entry.get("spdx_license_key") and not entry.get("is_exception")
            and not entry["spdx_license_key"].startswith("LicenseRef-")}


def doc_tables(text: str) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """(allowed ids, {purl: (reason, issue)}) from the policy doc's two tables."""
    allowed: list[str] = []
    exceptions: dict[str, tuple[str, str]] = {}
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        match = ROW.match(line.strip())
        if not match:
            continue
        key, rest = match.group(1).strip(), [c.strip() for c in match.group(2).rstrip().rstrip("|").split("|")]
        if section.startswith("allowed"):
            allowed.append(key)
        elif section.startswith("exceptions"):
            reason = rest[0] if rest else ""
            issue = rest[1] if len(rest) > 1 else ""
            exceptions[key] = (reason, issue)
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

    data: dict = {}
    config_path = root / CONFIG
    if not config_path.is_file():
        report(CONFIG, "LP-CONFIG", "missing")
    else:
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            data = loaded if isinstance(loaded, dict) else {}
            if not isinstance(loaded, dict):
                report(CONFIG, "LP-CONFIG", "not a YAML mapping")
        except yaml.YAMLError as exc:
            report(CONFIG, "LP-CONFIG", f"invalid YAML: {str(exc).splitlines()[0]}")

    allow = data.get("allow-licenses") or []
    if isinstance(allow, str):
        allow = [part.strip() for part in allow.split(",") if part.strip()]
    if config_path.is_file() and not allow and not any(f.startswith(f"{CONFIG}: LP-CONFIG") for f in findings):
        report(CONFIG, "LP-CONFIG", "allow-licenses is empty")
    if "deny-licenses" in data:
        report(CONFIG, "LP-DENY-OPTION", "deny-licenses is deprecated; use allow-licenses only")

    spdx = canonical_spdx_ids()
    for lic in allow:
        lic = str(lic)
        if DENIED.match(lic):
            report(CONFIG, "LP-DENIED", f"{lic} is not allowed by policy")
        if lic not in spdx:
            report(CONFIG, "LP-SPDX", f"{lic!r} is not a canonical SPDX licence id")

    exceptions = [str(p) for p in (data.get("allow-dependencies-licenses") or [])]
    doc_path = root / DOC
    doc_allowed: list[str] = []
    doc_exceptions: dict[str, tuple[str, str]] = {}
    if not doc_path.is_file():
        report(DOC, "LP-DOC", "missing policy document")
    else:
        doc_allowed, doc_exceptions = doc_tables(doc_path.read_text(encoding="utf-8"))
        if sorted(doc_allowed) != sorted(str(a) for a in allow):
            only_doc = sorted(set(doc_allowed) - set(map(str, allow)))
            only_cfg = sorted(set(map(str, allow)) - set(doc_allowed))
            report(DOC, "LP-DOC", f"allowlist differs from {CONFIG}: only in doc {only_doc}, only in config {only_cfg}")

    for purl in exceptions:
        if not valid_purl(purl):
            report(CONFIG, "LP-EXCEPTION", f"{purl!r} is not a valid package URL")
            continue
        reason, issue = doc_exceptions.get(purl, ("", ""))
        if purl not in doc_exceptions:
            report(DOC, "LP-EXCEPTION", f"{purl} is not documented")
        elif not reason or not ISSUE.match(issue):
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
