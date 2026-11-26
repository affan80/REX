#!/usr/bin/env python3
"""Docs integrity checker for REX (issue #39).

Checks every Markdown file tracked by git under --root:
  ADR-NAME          ADR files in docs/adr/ are named NNNN-kebab-title.md
  ADR-NUMBER        ADR numbers are unique and contiguous from 0001
  ADR-STATUS        front matter has a MADR 4 status (a superseding ADR must exist)
  ADR-DATE          front matter has a valid YYYY-MM-DD date
  ADR-INDEX         docs/adr/README.md exists and links every ADR
  ADR-INDEX-STATUS  the index's Status column matches each ADR's front matter
  LINK-BROKEN       relative links and images point at tracked files (exact case)
  DOCS-ENCODING     Markdown files are UTF-8
  DOCS-EMPTY        there is at least one tracked Markdown file
  DOCS-GIT          --root is a git work tree

Links are found with a CommonMark parser (markdown-it-py), so titles, <...>
destinations, reference links, multi-line link text, code spans, fences and
escapes behave as on GitHub. Targets are compared against `git ls-files`
with exact case, so a link that only works on a case-insensitive disk fails.

Output: one '<path>: <CODE> <detail>' line per finding; exit 1 if any, else 0.
Run: uv run --no-project --with markdown-it-py==4.3.0 python scripts/check_docs.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt

ADR_DIR = "docs/adr"
INDEX = f"{ADR_DIR}/README.md"
TEMPLATE = f"{ADR_DIR}/0000-template.md"
MD_SUFFIXES = {".md", ".markdown"}
ADR_NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
STATUS = re.compile(r"^(proposed|rejected|accepted|deprecated|superseded by ADR-(\d{4}))$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
# Relative links that leave the repository but are valid GitHub web routes.
WEB_ROUTES = {"issues", "pull", "pulls", "discussions", "wiki", "blob", "tree", "actions",
              "security", "releases", "compare", "commit", "commits", "labels", "milestones"}

MD = MarkdownIt("commonmark").enable("table")


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, path: str, code: str, detail: str) -> None:
        self.lines.append(f"{path}: {code} {detail}")


def tracked_files(root: Path) -> list[str] | None:
    proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached"],
                          capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return sorted(p for p in proc.stdout.decode("utf-8").split("\0") if p)


def read_text(root: Path, rel: str, report: Report) -> str | None:
    try:
        return (root / rel).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        report(rel, "DOCS-ENCODING", "not valid UTF-8")
    except OSError as exc:
        report(rel, "DOCS-ENCODING", f"unreadable: {exc.strerror}")
    return None


def front_matter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if line.startswith((" ", "\t", "#")):
            continue  # nested keys and comments are not top-level fields
        key, sep, value = line.partition(":")
        if not sep:
            continue
        value = value.strip()
        if value[:1] in {"'", '"'}:
            value = value[1:].split(value[0], 1)[0]
        else:
            value = value.split(" #", 1)[0].strip()
        fields[key.strip()] = value
    return {}


def link_targets(text: str) -> list[str]:
    """Hrefs of every link and image, as GitHub would render them."""
    targets: list[str] = []

    def walk(tokens) -> None:
        for tok in tokens:
            if tok.type == "link_open":
                targets.append(tok.attrGet("href") or "")
            elif tok.type == "image":
                targets.append(tok.attrGet("src") or "")
            if tok.children:
                walk(tok.children)

    walk(MD.parse(text))
    return targets


def resolve(source: str, target: str) -> str | None:
    """Repo-relative POSIX path for a local link, '' for links to ignore, None if it escapes."""
    if not target or target.startswith("#") or SCHEME.match(target) or target.startswith("//"):
        return ""
    local = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not local:
        return ""
    base = "" if local.startswith("/") else posixpath.dirname(source)
    joined = posixpath.normpath(posixpath.join(base, local.lstrip("/")))
    if joined == ".." or joined.startswith("../"):
        parts = joined.split("/")
        return "" if any(part in WEB_ROUTES for part in parts) else None
    return joined


def check_links(rel: str, text: str, files: set[str], dirs: set[str], report: Report) -> None:
    for target in link_targets(text):
        path = resolve(rel, target)
        if path == "":
            continue
        if path is None or (path not in files and path not in dirs):
            report(rel, "LINK-BROKEN", unquote(target.split("#", 1)[0]))


def index_rows(text: str) -> list[tuple[str, str]]:
    """(href, status) for each row of the first table with a Status column."""
    rows: list[tuple[str, str]] = []
    tokens = MD.parse(text)
    status_col, col, in_head, row_cells = None, 0, False, []
    for tok in tokens:
        if tok.type == "thead_open":
            in_head = True
        elif tok.type == "thead_close":
            in_head = False
        elif tok.type == "tr_open":
            col, row_cells = 0, []
        elif tok.type == "inline" and tok.map is not None and (in_head or status_col is not None):
            row_cells.append(tok)
            if in_head and tok.content.strip().lower() == "status":
                status_col = col
            col += 1
        elif tok.type == "tr_close" and not in_head and status_col is not None and row_cells:
            hrefs = link_targets(row_cells[0].content)
            status = row_cells[status_col].content.strip() if status_col < len(row_cells) else ""
            rows.append((hrefs[0] if hrefs else "", status))
    return rows


def check_adrs(root: Path, files: list[str], texts: dict[str, str], report: Report) -> int:
    if INDEX not in files:
        report(INDEX, "ADR-INDEX", "missing ADR index")
    numbered: dict[int, list[str]] = {}
    statuses: dict[str, str] = {}
    for rel in files:
        if posixpath.dirname(rel) != ADR_DIR or rel in {INDEX, TEMPLATE} or not rel.endswith(".md"):
            continue
        name = posixpath.basename(rel)
        match = ADR_NAME.match(name)
        if not match:
            report(rel, "ADR-NAME", "expected NNNN-kebab-title.md")
            continue
        numbered.setdefault(int(match.group(1)), []).append(rel)
        meta = front_matter(texts.get(rel, ""))
        statuses[name] = meta.get("status", "")
        date = meta.get("date", "")
        try:
            if not DATE.match(date):
                raise ValueError
            dt.date.fromisoformat(date)
        except ValueError:
            report(rel, "ADR-DATE", f"invalid or missing date {date!r}")
    for name, status in statuses.items():
        match = STATUS.match(status)
        if not match:
            report(f"{ADR_DIR}/{name}", "ADR-STATUS", f"invalid or missing status {status!r}")
        elif match.group(2) and int(match.group(2)) not in numbered:
            report(f"{ADR_DIR}/{name}", "ADR-STATUS", f"superseding ADR-{match.group(2)} does not exist")
    for number, paths in sorted(numbered.items()):
        if len(paths) > 1:
            for rel in paths:
                report(rel, "ADR-NUMBER", f"duplicate number {number:04d}")
    if sorted(numbered) != list(range(1, len(numbered) + 1)):
        report(ADR_DIR, "ADR-NUMBER", f"numbers {sorted(numbered)} are not contiguous from 1")
    if INDEX in texts:
        indexed: dict[str, str] = {}
        for href, status in index_rows(texts[INDEX]):
            path = resolve(INDEX, href)
            if path and posixpath.dirname(path) == ADR_DIR:
                indexed[posixpath.basename(path)] = status
        for name, status in sorted(statuses.items()):
            if name not in indexed:
                report(INDEX, "ADR-INDEX", f"missing {name}")
            elif indexed[name] != status:
                report(INDEX, "ADR-INDEX-STATUS", f"{name} is {status!r} but the index says {indexed[name]!r}")
    return sum(len(p) for p in numbered.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REX docs integrity checker")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args(argv).root.resolve()
    report = Report()

    files = tracked_files(root)
    if files is None:
        report(".", "DOCS-GIT", f"{root} is not a git work tree")
        print("\n".join(report.lines))
        return 1
    markdown = [f for f in files if posixpath.splitext(f)[1].lower() in MD_SUFFIXES]
    if not markdown:
        report(".", "DOCS-EMPTY", "no tracked Markdown files found")
    texts = {rel: text for rel in markdown if (text := read_text(root, rel, report)) is not None}
    file_set = set(files)
    dir_set = {posixpath.dirname(f) for f in files}
    dir_set |= {d.rsplit("/", i)[0] for d in list(dir_set) for i in range(1, d.count("/") + 1)}
    adr_count = check_adrs(root, files, texts, report)
    for rel, text in texts.items():
        check_links(rel, text, file_set, dir_set, report)
    if report.lines:
        print("\n".join(report.lines))
        return 1
    print(f"docs OK: {adr_count} ADRs, {len(markdown)} Markdown files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
