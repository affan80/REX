# Dependency licence policy

REX is licensed under the [Apache License 2.0](../../LICENSE) (hard rule 14). Every dependency (Python, JavaScript, GitHub Actions, container images and the analysis tools REX runs) must have a licence that lets us use and distribute REX under Apache-2.0.

**Approved by the owner on 2026-11-27.** Changes need an owner-approved pull request that updates the config, this page and the approved set in `scripts/license_policy.py` together.

## Source of truth

The machine-readable policy is [`.github/dependency-review-config.yml`](../../.github/dependency-review-config.yml):
- `allow-licenses` is the allowlist below;
- `allow-dependencies-licenses` holds the per-package exceptions below, as package URLs.

**Enforcement status:** nothing runs in CI yet.
- GitHub's dependency review (`actions/dependency-review-action`, `config-file`) is wired in #22 and checks the dependencies each pull request adds.
- osv-scanner is wired in #23 and checks the full lockfiles against the same list.
- Dependency review **only warns** about dependencies whose licence it cannot detect, so unknown licences are caught by osv-scanner (#23) and in pull-request review, not by dependency review.

`scripts/license_policy.py check` keeps the policy itself honest. It fails when:
- this page and the config disagree;
- an id isn't a canonical SPDX id, or isn't in the owner-approved set;
- an option would switch enforcement off (`license-check: false`, `warn-only: true`);
- an exception lacks a valid package URL, a reason or an issue.

Run it with:

```bash
uv run --no-project --with pyyaml==6.0.4 --with license-expression==30.4.4 \
  --with packageurl-python==0.17.6 --with markdown-it-py==4.3.0 \
  python scripts/license_policy.py check
```

## Allowed licences

Canonical [SPDX](https://spdx.org/licenses/) ids (SPDX License List 3.29). For an SPDX expression, `OR` passes if any side is allowed, and `AND` passes only if every part is allowed.

| SPDX id |
|---|
| `MIT` |
| `BSD-2-Clause` |
| `BSD-3-Clause` |
| `Apache-2.0` |
| `ISC` |
| `PSF-2.0` |
| `0BSD` |
| `CC0-1.0` |
| `Unlicense` |
| `Zlib` |
| `MPL-2.0` |

`MPL-2.0` is weak, file-level copyleft. Using an unmodified MPL library is fine. If you modify MPL-licensed files, those files stay MPL, and when you distribute them their source must be made available to recipients.

## Denied by default

| Licence family | Why |
|---|---|
| GPL-2.0 / GPL-3.0 (any variant) | Strong copyleft would extend to REX when the GPL code is linked into or combined with REX. Mere aggregation, such as a separate tool in the same image, is reviewed case by case. |
| AGPL-3.0 | Network copyleft: modifying AGPL code and offering it to users over a network requires providing its source, which would reach REX's service. |
| LGPL-2.1 / LGPL-3.0, as **linked** dependencies | Relinking and source obligations complicate distribution. |
| SSPL-1.0, BUSL-1.1 and other source-available licences | Not open source; they restrict use. |
| No licence, unknown, or "custom" (including `LicenseRef-*` ids such as `LicenseRef-clearlydefined-OTHER`) | No clear grant of rights. Ask the author, replace the dependency, or add a reviewed per-package exception. |

A denied licence can only be used through a documented **exception** (below), never by adding it to the allowlist.

## Dev-tool category

Some tools under a denied licence are acceptable because REX never links or distributes them: they only run as separate processes on developer machines or in CI. For example, Semgrep Community Edition is LGPL-2.1. Each such tool gets an exception entry: its package URL, why it's safe (not distributed, run as a process), and the issue that approved it.

Analysis tools that REX's workers run on samples (Ghidra, radare2, TShark and the others) are reviewed one by one in their adapter issues. They run as separate processes inside worker images, and the image licence review happens there.

## Exceptions

| Package | Reason | Issue |
|---|---|---|

No exceptions yet.

To add one:
1. Open an issue explaining the need.
2. Add the package URL (for example `pkg:pypi/semgrep`) to `allow-dependencies-licenses` in the config.
3. Add a row here with the package URL in backticks, the reason, and the issue (`#25`, `owner/repo#25`, or an issue or PR link).
4. Get the owner's approval in the pull request.

## Third-party notices

[`NOTICE`](../../NOTICE) carries REX's own attribution. When REX starts distributing third-party code (container images, bundled tools), their required notices are generated alongside the images (#23, Phase 0b).
