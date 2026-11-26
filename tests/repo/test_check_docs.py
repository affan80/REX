"""Red/green tests for scripts/check_docs.py (docs integrity checker, issue #39).

Each test builds a small git repository in a temp dir, runs the real checker
as a subprocess and asserts its exit code and the finding codes it reports.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "check_docs.py"

ADR_0001 = """---
status: accepted
date: 2026-11-27
---

# Record architecture decisions
"""

ADR_0002 = """---
status: proposed
date: 2026-11-28
---

# Choose a message broker
"""

INDEX = """# Architecture decision records

| ADR | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | accepted |
| [0002](0002-message-broker.md) | Choose a message broker | proposed |
"""


def valid_files() -> dict[str, str | bytes]:
    return {
        "README.md": "# Project\n\nSee [the ADRs](docs/adr/README.md).\n",
        "docs/adr/README.md": INDEX,
        "docs/adr/0000-template.md": "---\nstatus: proposed\ndate: 2026-01-01\n---\n\n# {title}\n",
        "docs/adr/0001-record-architecture-decisions.md": ADR_0001,
        "docs/adr/0002-message-broker.md": ADR_0002,
    }


def make_repo(root: Path, files: dict[str, str | bytes], untracked: dict[str, str] | None = None) -> Path:
    """Write files, `git add` them (tracked), then write `untracked` files without adding."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    for rel, text in (untracked or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def codes(result: subprocess.CompletedProcess[str]) -> set[str]:
    """Finding lines look like '<path>: <CODE> <detail>'."""
    found = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            found.add(parts[1])
    return found


def with_doc(text: str, extra: dict[str, str | bytes] | None = None) -> dict[str, str | bytes]:
    files = valid_files()
    files["CONTRIBUTING.md"] = text
    files.update(extra or {})
    return files


# --- the real repository -------------------------------------------------------


def test_the_real_repository_passes() -> None:
    result = run_checker(REPO)
    assert result.returncode == 0, result.stdout + result.stderr


# --- well-formed tree ------------------------------------------------------------


def test_well_formed_tree_passes(tmp_path: Path) -> None:
    result = run_checker(make_repo(tmp_path, valid_files()))
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "docs OK: 2 ADRs, 5 Markdown files"


def test_empty_repository_is_an_error_not_a_pass(tmp_path: Path) -> None:
    result = run_checker(make_repo(tmp_path, {}))
    assert result.returncode == 1
    assert "DOCS-EMPTY" in codes(result)


def test_directory_that_is_not_a_git_repository_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    result = run_checker(tmp_path)
    assert result.returncode == 1
    assert "DOCS-GIT" in codes(result)


# --- ADR files -------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    ["0003_Message_Broker.md", "3-message-broker.md", "0003-MessageBroker.md", "0003-.md"],
)
def test_badly_named_adr_is_rejected(tmp_path: Path, bad_name: str) -> None:
    files = valid_files()
    files[f"docs/adr/{bad_name}"] = ADR_0002
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-NAME" in codes(result)


def test_duplicate_adr_number_reports_every_file(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/0002-event-bus.md"] = ADR_0002
    files["docs/adr/README.md"] = INDEX + "| [0002](0002-event-bus.md) | Event bus | proposed |\n"
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert "docs/adr/0002-event-bus.md: ADR-NUMBER" in result.stdout
    assert "docs/adr/0002-message-broker.md: ADR-NUMBER" in result.stdout


def test_skipped_adr_number_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/0004-skips-three.md"] = ADR_0002
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-NUMBER" in codes(result)


@pytest.mark.parametrize(
    ("front_matter", "code"),
    [
        ("---\ndate: 2026-11-27\n---\n", "ADR-STATUS"),
        ("---\nstatus: approved\ndate: 2026-11-27\n---\n", "ADR-STATUS"),
        ("---\nstatus: superseded by 0001\ndate: 2026-11-27\n---\n", "ADR-STATUS"),
        ("---\nstatus: superseded by ADR-0099\ndate: 2026-11-27\n---\n", "ADR-STATUS"),
        ("---\nstatus: accepted\n---\n", "ADR-DATE"),
        ("---\nstatus: accepted\ndate: 2026-13-40\n---\n", "ADR-DATE"),
        ("---\nstatus: accepted\ndate: 27/11/2026\n---\n", "ADR-DATE"),
        ("# No front matter at all\n", "ADR-STATUS"),
    ],
)
def test_bad_front_matter_is_rejected(tmp_path: Path, front_matter: str, code: str) -> None:
    files = valid_files()
    files["docs/adr/0002-message-broker.md"] = front_matter + "\n# Choose a message broker\n"
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert code in codes(result)


@pytest.mark.parametrize(
    "status",
    ["proposed", "rejected", "accepted", "deprecated", "superseded by ADR-0001"],
)
def test_every_madr_status_is_accepted(tmp_path: Path, status: str) -> None:
    files = valid_files()
    files["docs/adr/0002-message-broker.md"] = (
        f"---\nstatus: {status}\ndate: 2026-11-28\n---\n\n# Choose a message broker\n"
    )
    files["docs/adr/README.md"] = INDEX.replace("message broker | proposed |", f"message broker | {status} |")
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize(
    "adr_text",
    [
        "﻿---\nstatus: proposed\ndate: 2026-11-28\n---\n\n# With a byte-order mark\n",
        "---\nstatus: proposed # owner to decide\ndate: '2026-11-28'\n---\n\n# Comment and quotes\n",
    ],
)
def test_harmless_front_matter_variants_pass(tmp_path: Path, adr_text: str) -> None:
    files = valid_files()
    files["docs/adr/0002-message-broker.md"] = adr_text
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 0, result.stdout


# --- ADR index -----------------------------------------------------------------


def test_adr_missing_from_index_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/0003-sandbox-technology.md"] = ADR_0002
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert "docs/adr/README.md: ADR-INDEX missing 0003-sandbox-technology.md" in result.stdout


def test_external_link_with_same_name_does_not_count_as_indexed(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/README.md"] = INDEX.replace(
        "[0002](0002-message-broker.md)", "[0002](https://example.com/0002-message-broker.md)"
    )
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-INDEX" in codes(result)


def test_index_status_must_match_the_adr(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/README.md"] = INDEX.replace("message broker | proposed |", "message broker | accepted |")
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-INDEX-STATUS" in codes(result)


def test_missing_index_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    del files["docs/adr/README.md"]
    files["README.md"] = "# Project\n"
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-INDEX" in codes(result)


def test_missing_adr_folder_is_rejected(tmp_path: Path) -> None:
    result = run_checker(make_repo(tmp_path, {"README.md": "# Project\n"}))
    assert result.returncode == 1
    assert "ADR-INDEX" in codes(result)


# --- links -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "doc",
    [
        "Read [the rules](missing.md).\n",
        "[x](missing.md 'single-quoted title')\n",
        "[x](missing.md (parenthesised title))\n",
        "[x](<no such file.md>)\n",
        "Reference [x][r].\n\n[r]: missing.md\n",
        "See [the long\nrules](missing.md) here.\n",
        "[![badge](README.md)](missing.md)\n",
        "![diagram](missing.png)\n",
        "```x```\n\n[after a one-line code span](missing.md)\n",
        "````\n```\n````\n\n[after a long fence](missing.md)\n",
        "[wrong case](DOCS/ADR/README.md)\n",
        "[typo escaping the repo](../CONTRIBUTING.md)\n",
        "[exists but untracked](notes.md)\n",
    ],
)
def test_broken_links_are_rejected(tmp_path: Path, doc: str) -> None:
    root = make_repo(tmp_path, with_doc(doc), untracked={"notes.md": "# local only\n"})
    result = run_checker(root)
    assert result.returncode == 1, result.stdout
    assert "LINK-BROKEN" in codes(result)


@pytest.mark.parametrize(
    ("doc", "extra"),
    [
        ("[spaces](my%20file.md)\n", {"my file.md": "# x\n"}),
        ("[spaces](<my file.md>)\n", {"my file.md": "# x\n"}),
        ("[parens](a_(b).md)\n", {"a_(b).md": "# x\n"}),
        ("[dir](docs/adr/)\n", {}),
        ("[anchor](docs/adr/README.md#process)\n", {}),
        ("[web](https://example.com/x.md) [mail](mailto:a@b.c) [here](#rules)\n", {}),
        ("[issue](../../issues/111) [pr](../../pull/112)\n", {}),
        ("```\n[in a fence](nope.md)\n```\n", {}),
        ("    [in an indented code block](nope.md)\n", {}),
        ("Inline `[x](nope.md)` code.\n", {}),
        ("Escaped \\[x\\](nope.md) brackets.\n", {}),
    ],
)
def test_valid_or_non_file_links_pass(tmp_path: Path, doc: str, extra: dict[str, str]) -> None:
    result = run_checker(make_repo(tmp_path, with_doc(doc, extra)))
    assert result.returncode == 0, result.stdout


def test_markdown_under_dot_github_is_checked(tmp_path: Path) -> None:
    files = with_doc("# ok\n", {".github/pull_request_template.md": "See [rules](CONTRIBUTING.md) and [x](gone.md).\n"})
    result = run_checker(make_repo(tmp_path, files))
    assert result.returncode == 1
    assert ".github/pull_request_template.md: LINK-BROKEN gone.md" in result.stdout


def test_untracked_markdown_is_not_checked(tmp_path: Path) -> None:
    root = make_repo(tmp_path, valid_files(), untracked={"venv/lib/README.md": "[broken](nowhere.md)\n"})
    result = run_checker(root)
    assert result.returncode == 0, result.stdout


def test_non_utf8_markdown_is_a_finding_not_a_crash(tmp_path: Path) -> None:
    result = run_checker(make_repo(tmp_path, with_doc("# ok\n", {"notes.md": b"\xff\xfe broken \x80\n"})))
    assert result.returncode == 1
    assert "DOCS-ENCODING" in codes(result)
    assert "Traceback" not in result.stderr
