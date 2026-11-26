#!/usr/bin/env python3
"""Docs integrity checker for REX (issue #39).

Checks, for every Markdown file under --root (skipping hidden and dependency dirs):
  ADR-NAME     ADR files in docs/adr/ are named NNNN-kebab-title.md
  ADR-NUMBER   ADR numbers are unique and contiguous from 0001
  ADR-STATUS   front matter has a MADR 4 status
  ADR-DATE     front matter has a valid YYYY-MM-DD date
  ADR-INDEX    docs/adr/README.md links every ADR
  LINK-BROKEN  relative links point at files that exist
  DOCS-EMPTY   there is at least one Markdown file to check

Output: one '<path>: <CODE> <detail>' line per finding; exit 1 if any, else 0.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

SKIP_DIRS = {"node_modules", "__pycache__"}
ADR_DIR = Path("docs/adr")
TEMPLATE = "0000-template.md"
ADR_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
STATUS = re.compile(r"^(proposed|rejected|accepted|deprecated|superseded by ADR-\d{4})$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#)", re.IGNORECASE)


def markdown_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        files.append(path)
    return sorted(files)


def front_matter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip("\"'")
    return {}


def links(text: str) -> list[str]:
    found, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if not in_fence:
            found += LINK.findall(INLINE_CODE.sub("", line))
    return found


def check_adrs(root: Path, report) -> int:
    adr_dir = root / ADR_DIR
    if not adr_dir.is_dir():
        return 0
    numbered: dict[int, list[Path]] = {}
    for path in sorted(adr_dir.glob("*.md")):
        if path.name in {"README.md", TEMPLATE}:
            continue
        match = ADR_NAME.match(path.name)
        if not match:
            report(path, "ADR-NAME", "expected NNNN-kebab-title.md")
            continue
        numbered.setdefault(int(match.group(1)), []).append(path)
        meta = front_matter(path.read_text(encoding="utf-8"))
        if not STATUS.match(meta.get("status", "")):
            report(path, "ADR-STATUS", f"invalid or missing status {meta.get('status', '')!r}")
        date = meta.get("date", "")
        try:
            if not DATE.match(date):
                raise ValueError
            dt.date.fromisoformat(date)
        except ValueError:
            report(path, "ADR-DATE", f"invalid or missing date {date!r}")
    for number, paths in numbered.items():
        if len(paths) > 1:
            report(paths[1], "ADR-NUMBER", f"duplicate number {number:04d}")
    expected = list(range(1, len(numbered) + 1))
    if sorted(numbered) != expected:
        report(adr_dir, "ADR-NUMBER", f"numbers {sorted(numbered)} are not contiguous from 1")
    index = adr_dir / "README.md"
    indexed = set()
    if index.exists():
        indexed = {Path(target.split("#")[0]).name for target in links(index.read_text(encoding="utf-8"))}
    for paths in numbered.values():
        for path in paths:
            if path.name not in indexed:
                report(index, "ADR-INDEX", f"missing {path.name}")
    return sum(len(p) for p in numbered.values())


def check_links(root: Path, path: Path, report) -> None:
    for target in links(path.read_text(encoding="utf-8")):
        if EXTERNAL.match(target):
            continue
        local = target.split("#", 1)[0].split("?", 1)[0]
        if not local:
            continue
        resolved = (root / local.lstrip("/")) if local.startswith("/") else (path.parent / local)
        resolved = resolved.resolve()
        if not resolved.is_relative_to(root):
            continue  # GitHub web routes such as ../../issues/1
        if not resolved.exists():
            report(path, "LINK-BROKEN", local)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args(argv).root.resolve()
    findings: list[str] = []

    def report(path: Path, code: str, detail: str) -> None:
        rel = path.relative_to(root) if path != root else Path(".")
        findings.append(f"{rel.as_posix()}: {code} {detail}")

    files = markdown_files(root)
    if not files:
        report(root, "DOCS-EMPTY", "no Markdown files found")
    adr_count = check_adrs(root, report)
    for path in files:
        check_links(root, path, report)
    if findings:
        print("\n".join(findings))
        return 1
    print(f"docs OK: {adr_count} ADRs, {len(files)} Markdown files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
