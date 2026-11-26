"""Red/green tests for scripts/check_docs.py (docs integrity checker, issue #39).

Each test builds a small docs tree in a temp dir, runs the real checker as a
subprocess and asserts its exit code and the finding codes it reports.
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


def make_tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def valid_files() -> dict[str, str]:
    return {
        "README.md": "# Project\n\nSee [the ADRs](docs/adr/README.md).\n",
        "docs/adr/README.md": INDEX,
        "docs/adr/0000-template.md": "---\nstatus: proposed\ndate: 2026-01-01\n---\n\n# {title}\n",
        "docs/adr/0001-record-architecture-decisions.md": ADR_0001,
        "docs/adr/0002-message-broker.md": ADR_0002,
    }


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def codes(result: subprocess.CompletedProcess[str]) -> set[str]:
    """Finding codes are the second whitespace-separated field: '<path>: <CODE> <message>'."""
    found = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            found.add(parts[1])
    return found


def test_well_formed_tree_passes(tmp_path: Path) -> None:
    result = run_checker(make_tree(tmp_path, valid_files()))
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "docs OK: 2 ADRs, 5 Markdown files"


@pytest.mark.parametrize(
    "bad_name",
    ["0003_Message_Broker.md", "3-message-broker.md", "0003-MessageBroker.md", "0003-.md"],
)
def test_badly_named_adr_is_rejected(tmp_path: Path, bad_name: str) -> None:
    files = valid_files()
    files[f"docs/adr/{bad_name}"] = ADR_0002
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-NAME" in codes(result)


def test_duplicate_adr_number_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/0002-event-bus.md"] = ADR_0002
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-NUMBER" in codes(result)


def test_skipped_adr_number_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/0004-skips-three.md"] = ADR_0002
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-NUMBER" in codes(result)


@pytest.mark.parametrize(
    ("front_matter", "code"),
    [
        ("---\ndate: 2026-11-27\n---\n", "ADR-STATUS"),
        ("---\nstatus: approved\ndate: 2026-11-27\n---\n", "ADR-STATUS"),
        ("---\nstatus: superseded by 0001\ndate: 2026-11-27\n---\n", "ADR-STATUS"),
        ("---\nstatus: accepted\n---\n", "ADR-DATE"),
        ("---\nstatus: accepted\ndate: 2026-13-40\n---\n", "ADR-DATE"),
        ("---\nstatus: accepted\ndate: 27/11/2026\n---\n", "ADR-DATE"),
        ("# No front matter at all\n", "ADR-STATUS"),
    ],
)
def test_bad_front_matter_is_rejected(tmp_path: Path, front_matter: str, code: str) -> None:
    files = valid_files()
    files["docs/adr/0002-message-broker.md"] = front_matter + "\n# Choose a message broker\n"
    result = run_checker(make_tree(tmp_path, files))
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
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 0, result.stdout


def test_adr_missing_from_index_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/0003-sandbox-technology.md"] = ADR_0002
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 1
    assert "ADR-INDEX" in codes(result)


def test_broken_relative_link_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    files["CONTRIBUTING.md"] = "Read [the rules](docs/rules.md) and [ADR 1](docs/adr/0001-record-architecture-decisions.md).\n"
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 1
    assert "LINK-BROKEN" in codes(result)
    assert "CONTRIBUTING.md: LINK-BROKEN docs/rules.md" in result.stdout


def test_index_link_to_missing_adr_is_rejected(tmp_path: Path) -> None:
    files = valid_files()
    files["docs/adr/README.md"] = INDEX + "| [0009](0009-ghost.md) | Ghost | proposed |\n"
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 1
    assert "LINK-BROKEN" in codes(result)


def test_links_that_are_not_local_files_are_ignored(tmp_path: Path) -> None:
    files = valid_files()
    files["CONTRIBUTING.md"] = (
        "[web](https://example.com/x.md) [mail](mailto:a@b.c) [anchor](#rules) "
        "[issue](../../issues/111) [file anchor](docs/adr/README.md#process)\n"
        "```\n[inside a code fence](not/a/file.md)\n```\n"
        "Inline code `[x](nope.md)` is ignored too.\n"
    )
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 0, result.stdout


def test_hidden_and_dependency_dirs_are_skipped(tmp_path: Path) -> None:
    files = valid_files()
    files["node_modules/pkg/README.md"] = "[broken](nowhere.md)\n"
    files[".venv/lib/README.md"] = "[broken](nowhere.md)\n"
    result = run_checker(make_tree(tmp_path, files))
    assert result.returncode == 0, result.stdout


def test_empty_tree_is_an_error_not_a_pass(tmp_path: Path) -> None:
    result = run_checker(tmp_path)
    assert result.returncode == 1
    assert "DOCS-EMPTY" in codes(result)
