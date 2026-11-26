"""Red/green tests for scripts/license_policy.py (dependency licence policy, issue #38).

Each test writes a policy config and policy doc into a temp dir, runs the real
checker as a subprocess, and asserts its exit code and finding codes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "license_policy.py"

ALLOW = ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0",
         "0BSD", "CC0-1.0", "Unlicense", "Zlib", "MPL-2.0"]


def config(allow: list[str] | None = None, exceptions: list[str] | None = None, extra: str = "") -> str:
    lines = ["fail-on-severity: high", "allow-licenses:"]
    lines += [f"  - {lic}" for lic in (ALLOW if allow is None else allow)]
    if exceptions:
        lines.append("allow-dependencies-licenses:")
        lines += [f"  - {purl}" for purl in exceptions]
    return "\n".join(lines) + "\n" + extra


def doc(allow: list[str] | None = None, exceptions: list[tuple[str, str, str]] | None = None) -> str:
    rows = "\n".join(f"| `{lic}` |" for lic in (ALLOW if allow is None else allow))
    exc_rows = "\n".join(f"| `{p}` | {reason} | {issue} |" for p, reason, issue in (exceptions or []))
    return (
        "# Dependency licences\n\n## Allowed licences\n\n| SPDX id |\n|---|\n" + rows + "\n\n"
        "## Exceptions\n\n| Package | Reason | Issue |\n|---|---|---|\n" + exc_rows + "\n"
    )


def make(root: Path, config_text: str | None, doc_text: str | None) -> Path:
    if config_text is not None:
        (root / ".github").mkdir(parents=True, exist_ok=True)
        (root / ".github" / "dependency-review-config.yml").write_text(config_text, encoding="utf-8")
    if doc_text is not None:
        (root / "docs" / "security").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "security" / "dependency-licenses.md").write_text(doc_text, encoding="utf-8")
    return root


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CHECKER), "check", "--root", str(root)],
                          capture_output=True, text=True, check=False)


def codes(result: subprocess.CompletedProcess[str]) -> set[str]:
    return {line.split()[1] for line in result.stdout.splitlines()
            if len(line.split()) >= 2 and line.split()[0].endswith(":")}


def test_the_real_repository_passes() -> None:
    result = run(REPO)
    assert result.returncode == 0, result.stdout + result.stderr


def test_valid_policy_passes(tmp_path: Path) -> None:
    result = run(make(tmp_path, config(), doc()))
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "licence policy OK: 11 allowed licences, 0 exceptions"


def test_valid_policy_with_documented_exception_passes(tmp_path: Path) -> None:
    purl = "pkg:pypi/semgrep"
    result = run(make(tmp_path, config(exceptions=[purl]),
                      doc(exceptions=[(purl, "LGPL-2.1 dev tool, run as a process, never distributed", "#25")])))
    assert result.returncode == 0, result.stdout
    assert "1 exceptions" in result.stdout


def test_missing_config_is_rejected(tmp_path: Path) -> None:
    result = run(make(tmp_path, None, doc()))
    assert result.returncode == 1
    assert "LP-CONFIG" in codes(result)


def test_empty_allowlist_is_rejected(tmp_path: Path) -> None:
    result = run(make(tmp_path, "fail-on-severity: high\nallow-licenses: []\n", doc(allow=[])))
    assert result.returncode == 1
    assert "LP-CONFIG" in codes(result)


@pytest.mark.parametrize("bad", ["Apache 2.0", "MIT License", "BSD", "GPL-2.0", "not-a-licence"])
def test_non_spdx_or_deprecated_id_is_rejected(tmp_path: Path, bad: str) -> None:
    allow = ALLOW + [bad]
    result = run(make(tmp_path, config(allow=allow), doc(allow=allow)))
    assert result.returncode == 1
    assert "LP-SPDX" in codes(result)


@pytest.mark.parametrize("denied", ["GPL-3.0-only", "AGPL-3.0-or-later", "LGPL-2.1-only", "SSPL-1.0", "BUSL-1.1"])
def test_copyleft_or_source_available_in_allowlist_is_rejected(tmp_path: Path, denied: str) -> None:
    allow = ALLOW + [denied]
    result = run(make(tmp_path, config(allow=allow), doc(allow=allow)))
    assert result.returncode == 1
    assert "LP-DENIED" in codes(result)


def test_deprecated_deny_licenses_option_is_rejected(tmp_path: Path) -> None:
    result = run(make(tmp_path, config(extra="deny-licenses:\n  - GPL-3.0-only\n"), doc()))
    assert result.returncode == 1
    assert "LP-DENY-OPTION" in codes(result)


@pytest.mark.parametrize("bad_purl", ["semgrep", "pypi/semgrep", "pkg:/semgrep", "pkg:pypi/"])
def test_invalid_exception_purl_is_rejected(tmp_path: Path, bad_purl: str) -> None:
    result = run(make(tmp_path, config(exceptions=[bad_purl]), doc(exceptions=[(bad_purl, "reason", "#25")])))
    assert result.returncode == 1
    assert "LP-EXCEPTION" in codes(result)


def test_undocumented_exception_is_rejected(tmp_path: Path) -> None:
    result = run(make(tmp_path, config(exceptions=["pkg:pypi/semgrep"]), doc()))
    assert result.returncode == 1
    assert "LP-EXCEPTION" in codes(result)


@pytest.mark.parametrize(("reason", "issue"), [("", "#25"), ("dev tool", ""), ("dev tool", "soon")])
def test_exception_without_reason_or_issue_is_rejected(tmp_path: Path, reason: str, issue: str) -> None:
    purl = "pkg:pypi/semgrep"
    result = run(make(tmp_path, config(exceptions=[purl]), doc(exceptions=[(purl, reason, issue)])))
    assert result.returncode == 1
    assert "LP-EXCEPTION" in codes(result)


def test_doc_allowlist_drifting_from_config_is_rejected(tmp_path: Path) -> None:
    result = run(make(tmp_path, config(), doc(allow=[lic for lic in ALLOW if lic != "MPL-2.0"])))
    assert result.returncode == 1
    assert "LP-DOC" in codes(result)


def test_missing_policy_doc_is_rejected(tmp_path: Path) -> None:
    result = run(make(tmp_path, config(), None))
    assert result.returncode == 1
    assert "LP-DOC" in codes(result)


def test_malformed_yaml_is_a_finding_not_a_crash(tmp_path: Path) -> None:
    result = run(make(tmp_path, "allow-licenses: [MIT\n", doc()))
    assert result.returncode == 1
    assert "LP-CONFIG" in codes(result)
    assert "Traceback" not in result.stderr


# --- review round 1 (PR #115) ------------------------------------------------------


@pytest.mark.parametrize("not_approved", ["EUPL-1.2", "CC-BY-SA-4.0", "OSL-3.0", "Elastic-2.0", "CC-BY-NC-4.0", "CPAL-1.0"])
def test_any_licence_outside_the_owner_approved_set_is_rejected(tmp_path: Path, not_approved: str) -> None:
    allow = ALLOW + [not_approved]
    result = run(make(tmp_path, config(allow=allow), doc(allow=allow)))
    assert result.returncode == 1
    assert "LP-DENIED" in codes(result)


@pytest.mark.parametrize(
    "option",
    ["license-check: false\n", "warn-only: true\n"],
)
def test_options_that_disable_enforcement_are_rejected(tmp_path: Path, option: str) -> None:
    result = run(make(tmp_path, config(extra=option), doc()))
    assert result.returncode == 1
    assert "LP-CONFIG" in codes(result)


def test_comma_separated_allowlist_string_is_accepted(tmp_path: Path) -> None:
    text = "fail-on-severity: high\nallow-licenses: '" + ", ".join(ALLOW) + "'\n"
    result = run(make(tmp_path, text, doc()))
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize(
    "value",
    ["pkg:pypi/semgrep", "'pkg:pypi/semgrep, pkg:npm/pyright'"],
)
def test_scalar_or_comma_separated_exceptions_are_accepted(tmp_path: Path, value: str) -> None:
    purls = [p.strip() for p in value.strip("'").split(",")]
    text = config() + f"allow-dependencies-licenses: {value}\n"
    result = run(make(tmp_path, text, doc(exceptions=[(p, "dev tool, run as a process", "#25") for p in purls])))
    assert result.returncode == 0, result.stdout
    assert f"{len(purls)} exceptions" in result.stdout


@pytest.mark.parametrize(
    "text",
    [
        "allow-licenses:\n  MIT: true\n",
        config() + "allow-dependencies-licenses:\n  pkg:pypi/semgrep: yes\n",
        config() + "allow-licenses:\n  - MIT\n",  # duplicate key: the action's YAML parser rejects it
    ],
)
def test_shapes_the_action_rejects_are_rejected(tmp_path: Path, text: str) -> None:
    result = run(make(tmp_path, text, doc()))
    assert result.returncode == 1
    assert "LP-CONFIG" in codes(result)


def test_exception_documented_but_missing_from_config_is_rejected(tmp_path: Path) -> None:
    result = run(make(tmp_path, config(), doc(exceptions=[("pkg:pypi/semgrep", "dev tool", "#25")])))
    assert result.returncode == 1
    assert "LP-DOC" in codes(result)


@pytest.mark.parametrize(
    "issue",
    ["#25", "[#25](https://github.com/affan80/REX/issues/25)", "affan80/REX#25",
     "https://github.com/affan80/REX/issues/25"],
)
def test_common_issue_reference_forms_are_accepted(tmp_path: Path, issue: str) -> None:
    purl = "pkg:pypi/semgrep"
    result = run(make(tmp_path, config(exceptions=[purl]), doc(exceptions=[(purl, "dev tool, run as a process", issue)])))
    assert result.returncode == 0, result.stdout


def test_issue_reference_in_the_reason_column_is_rejected(tmp_path: Path) -> None:
    purl = "pkg:pypi/semgrep"
    result = run(make(tmp_path, config(exceptions=[purl]), doc(exceptions=[(purl, "#25", "")])))
    assert result.returncode == 1
    assert "LP-EXCEPTION" in codes(result)


def test_duplicate_allowlist_entry_is_rejected(tmp_path: Path) -> None:
    allow = ALLOW + ["MIT"]
    result = run(make(tmp_path, config(allow=allow), doc(allow=allow)))
    assert result.returncode == 1
    assert "LP-CONFIG" in codes(result)


def test_rows_inside_code_fences_are_not_part_of_the_allowlist(tmp_path: Path) -> None:
    text = doc().replace("## Exceptions", "```\n| `GPL-3.0-only` |\n```\n\n## Exceptions")
    result = run(make(tmp_path, config(), text))
    assert result.returncode == 0, result.stdout
