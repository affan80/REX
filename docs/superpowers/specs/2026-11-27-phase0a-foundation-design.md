# Phase 0a: Repo Foundation and Guardrails — Design (v2)

Status: Draft v2 for owner approval — revised after (a) builder check, (b) adversarial security review, (c) Claude Code docs verification, (d) latest-version research. Versions verified 2026-11-27.
Issues: #1 (ADR workspace), #18–#26, #32–#33, #35–#40. PR bodies say "Refs #N"; an issue is closed only when all its acceptance criteria are met; partially covered issues get a comment listing what moved to 0b.
Phase 0b (separate design): #41 contracts, #42 shared config + log redaction, #43 Compose, #28 images, #29 contracts CI, #31 release workflow, #34 `.env.example` + compose recipes, Docker coverage in Dependabot/licenses/SBOM (#22–#24), TS boundary check (#26), MCP servers for Postgres/Playwright (#35), SBOM release attachment + attestation (#24).

## 1. Intent

REX handles hostile artifacts and lives in a **public** GitHub repo with a **sole maintainer**. Before any product code exists, the repo must make REX's hard rules hard to break by accident — by a person, by CI, or by an AI agent. Phase 0a builds that guardrail layer so every later PR lands inside it.

Success means each of these fails CI (and pre-commit where it applies), proven by a test that watches it fail:
- a secret-shaped token; a committed executable/archive/sample, an executable bit, or a symlink;
- a cross-service import, a worker importing a service, or a shared package importing either;
- artifact parsing, process spawning or dynamic import in `services/api`;
- an unpinned or dangerous GitHub workflow;
- a dependency with a denied or unknown license;

…and an AI agent in this repo cannot read, edit or execute files in the samples directories, enforced by the OS sandbox, not just by instructions.

## 2. Goals, non-goals, anti-goals

Goals: layout + uv/pnpm/just workspaces on current toolchains; docs base (LICENSE/NOTICE, ADRs 0001–0002, CONTRIBUTING, SECURITY, threat model v1, architecture overview); agent guardrails (CLAUDE.md, sandbox, deny rules, fail-closed hook); CI guards with tests; security scanning; governance and repo settings that a sole maintainer can actually merge under.

Non-goals: product code (service/worker dirs get a README only); Compose, contracts, images, releases (0b); deciding any other open ADR (#2–#17).

Anti-goals (failure even if it "works"):
- Any real sample, binary, or secret-shaped string ever reaching public git history.
- A check that passes because it silently ran on nothing (zero packages, zero files, skipped job).
- Required checks that can deadlock merges, or a ruleset the maintainer must bypass to merge.
- Guards that fail **open** on error.
- Copying proprietary-licensed rules (Semgrep registry) into this Apache-2.0 repo.

## 3. Constraints

- Hard rules 1–14 and working rules in CLAUDE.md (the owner's project context, verbatim).
- Public repo: CodeQL, dependency review, secret scanning are free. Already on: secret scanning, push protection. Off today: Dependabot alerts/security updates, non-provider secret patterns.
- Sole maintainer: GitHub never counts an author's own approval.
- Every guard ships with a test that fails without the guard (TDD; security change ⇒ regression test).
- Host today: uv 0.11.29, pnpm 10.16, Node 22, Python 3.15, Docker 29 — older than current (§5.2, §8).

## 4. Approaches

### 4.1 Workspace tooling — ADR-0002 (owner decided)
| Option | Complexity | Fit | Verdict |
|---|---|---|---|
| uv workspaces + pnpm workspaces + justfile | Low | Native per language; permissive licenses; fastest | **Chosen** |
| Nx + Python plugin | Med–High | Cross-language task graph/cache; Python via community plugin | Rejected: more moving parts to trust |
| Pants | High | Hermetic, strong Python | Rejected: learning curve for a solo maintainer |
Consequences: no cross-language build cache (CI uses job-level change detection); each language is upgraded independently. ADR-0002 is written in the standard ADR format (Context, Decision, Options with assessment tables, Trade-offs, Consequences, Action items).

### 4.2 How guards are proven (my call)
A pytest suite in `tests/repo/` exercises every guard against fixtures **generated at test time in `tmp_path`** (never committed: no secret-shaped strings, no binaries in history). It runs locally (`just guards`) and as a CI job. Rejected: CI-only fixture jobs (hard to run locally, easy to skip silently).

### 4.3 Action pinning
| Option | Verdict |
|---|---|
| Full-SHA pin every `uses:` + Dependabot updates | **Chosen**: works everywhere and Scorecard recognizes it |
| GitHub workflow lockfiles (`actions.lock`, GA 2026-10-28) | Deferred: new; doesn't cover reusable workflows; Scorecard recognition unconfirmed. Revisit in 0b. |

### 4.4 License checking
| Option | Verdict |
|---|---|
| pip-licenses + pnpm license-checker + custom SPDX logic | Rejected: reads only the installed env, emits non-SPDX names, mishandles `OR`/`AND` |
| **osv-scanner `--licenses` allowlist** (reads `uv.lock` + `pnpm-lock.yaml` directly, SPDX ids via deps.dev) **+ dependency-review `allow-licenses`** as a second, lockfile-based gate | **Chosen** |

### 4.5 Scope split and delivery (owner decided)
Phase 0a then 0b; stacked PRs, one per concern (§6).

## 5. Design

### 5.1 Layout and naming
All directories from CLAUDE.md are created; dirs without code get a `README.md` (purpose, owning phase/issue). Package naming (my call): Python src layout, import name `rex_<dir>` with hyphens → underscores (`services/api/src/rex_api`, `workers/analysis/src/rex_worker_analysis`, `packages/contracts/src/rex_contracts`), distribution names hyphenated (`rex-api`); TS packages `@rex/<dir>`.

Root files: `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `NOTICE`, `justfile`, `pyproject.toml`, `uv.lock`, `.python-version`, `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `tsconfig.base.json`, `eslint.config.js`, `.pre-commit-config.yaml`, `.gitleaks.toml`, `.gitignore`, `.gitattributes`, `.editorconfig`, `osv-scanner.toml`, `.importlinter` (generated), `.claude/settings.json`, `.claude/hooks/guard_samples.py`, `.github/…`, `semgrep/rules/*`, `semgrep/tests/*`, `scripts/*`, `tests/repo/*`, `docs/adr/*`, `docs/security/*`, `docs/architecture/overview.md`, `docs/operations/repo-settings.md`.

### 5.2 Toolchain (latest stable, verified 2026-11-27)
| Tool | Version / setting | Notes |
|---|---|---|
| Python | `.python-version` = 3.15; `requires-python = ">=3.13"`; CI matrix 3.13 / 3.14 / 3.15 | 3.15.2 latest |
| uv | `required-version = ">=0.13.10"`; `exclude-newer = "7 days"` (release cooldown); `no-build = true` (no sdist build scripts) | CI: `uv sync --locked` |
| Node | 26 (Active LTS), `engines.node = ">=26"` | Corepack was removed from Node 25+, so pnpm comes from `pnpm/action-setup` in CI and a pinned install locally |
| pnpm | 12.x, `packageManager: "pnpm@12.23.0"` | Settings only in `pnpm-workspace.yaml` (pnpm 12 fails on unknown keys): `minimumReleaseAge: 10080`, `allowBuilds: {}`; `strictDepBuilds`/`blockExoticSubdeps` on by default. CI: `pnpm install --frozen-lockfile` |
| TypeScript | **6.0.x pinned** | typescript-eslint 8.74 requires `<6.1`; TS 7 (Go-native, no JS API yet) revisited when 7.1 ships an API. No `baseUrl` (removed in TS 7) |
| ESLint | 10.x flat config + typescript-eslint 8.74 | |
| Ruff | 0.17.x, rules: defaults + `S` (bandit) + `B` | |
| pyright | 1.1.414 | `ty` is still beta: not used |
| import-linter | 2.17 | repo moved to `import-linter/import-linter` |
| Semgrep CE | 1.187, LGPL-2.1, **dev-tool license exception** | REX's own rules are the blocking gate; registry packs only via `--config p/…` at CI time, never vendored (Semgrep Rules License) |
| gitleaks | binary v8.30.1 pinned by version + SHA-256 (MIT) | Not gitleaks-action (non-MIT; needs a key for org repos). Pre-commit uses the `gitleaks-system` hook (no Go toolchain) |
| osv-scanner | v2.7.1 (vulnerabilities + licenses) | Official reusable workflows pinned by SHA |
| pre-commit | 4.7, `rev:` pinned to SHAs (`autoupdate --freeze`) | prek (0.x) considered; not yet |
| zizmor, actionlint | pinned | workflow security lint |
| just | latest via brew | owner-approved install |

Dev tools (pytest, ruff, pyright, import-linter, semgrep, pre-commit, zizmor, pyyaml) live in a **locked** uv dependency group, so their transitive dependencies are locked too (not `uvx` with a floating resolve). Binary tools (gitleaks, osv-scanner, actionlint) are downloaded in CI by pinned version and checked against SHA-256.

`justfile` recipes: `setup`, `lint`, `typecheck`, `test`, `guards`, `licenses`, `precommit`, `importlinter-gen`.

### 5.3 Agent guardrails (Claude Code)
CLAUDE.md is **guidance**; enforcement lives in settings, the sandbox and the hook.

- `CLAUDE.md`: the owner's REX project context verbatim (under 200 lines), plus "Repo conventions" (just recipes, sample handling, ADR process, "CLAUDE.md overrides plugin defaults").
- **Sample handling convention:** real samples live only outside the repo in `~/.rex-samples/`, stored as password-protected archives (password `infected`, the industry convention), so an accidental read returns ciphertext. Repo-local `.rex-samples/` and `quarantine/` are git-ignored and denied as well.
- `.claude/settings.json` (committed):
  - `permissions.deny`: `Read`/`Edit` of `~/.rex-samples/**`, `**/.rex-samples/**`, `**/quarantine/**`, `**/.env`, `**/.env.local`, `**/.env.*.local`. Secrets live only in those names; `.env.example` stays readable. `Edit` deny also covers Write and NotebookEdit. Also deny `Edit(.claude/**)` so an agent can't weaken its own guards (humans edit those files).
  - `permissions.disableBypassPermissionsMode: "disable"`.
  - `sandbox`: `enabled: true`, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`, `filesystem.denyRead`/`denyWrite` for `~/.rex-samples`, `./.rex-samples`, `./quarantine`, `~/.ssh`, `~/.aws`; `network.allowedDomains` limited to the hosts development needs (github.com, api.github.com, objects.githubusercontent.com, pypi.org, files.pythonhosted.org, registry.npmjs.org, nodejs.org). The OS-level sandbox (Seatbelt on macOS) is the real boundary for shell commands. Deny rules cover the built-in file tools, which the sandbox does not wrap.
  - Hook: `PreToolUse`, matcher `Bash|Read|Edit|Write|NotebookEdit|Grep|Glob|mcp__.*`, exec form (`python3` + `${CLAUDE_PROJECT_DIR}/.claude/hooks/guard_samples.py`). It is a **tripwire with clear messages**, not the boundary.
- `guard_samples.py`: reads hook JSON from stdin; for file tools checks `file_path`/`notebook_path`/`path` (a missing path means the project root) after `realpath` (catches symlinks); for Bash flags references to sample paths, including `$HOME`/`~` forms and globs like `.rex-s*`. Blocks with **exit 2** plus a reason on stderr. The whole body is wrapped so any exception also exits 2 (**fail closed**).
- Tests (`tests/repo/test_guard_samples.py`): run the real script as a subprocess with real hook JSON for each tool, and assert exit 2 on block cases (direct, `~`, `$HOME`, symlink, glob, Grep path, malformed JSON) and exit 0 on normal cases. `test_claude_settings.py` parses `.claude/settings.json` and asserts the hook wiring (matcher, exec path), the deny entries, the sandbox block and `disableBypassPermissionsMode`.
- Plugins stay personal (owner decision). CONTRIBUTING documents superpowers and ponytail as optional, with "leave ponytail's webhook empty".
- `.gitignore` adds `.claude/settings.local.json`, `CLAUDE.local.md`, `.env`, `.env.local`, `.env.*.local`, `.rex-samples/`, `quarantine/`.
- No `.mcp.json` in 0a (#35 → 0b).

### 5.4 Preventing samples, binaries and secrets in git
- `scripts/check_no_binaries.py`, run as a pre-commit hook **and** as a CI step over `git diff --name-only <base>...HEAD`, so `--no-verify` doesn't skip it. It rejects:
  - files whose magic bytes match executables (`MZ`, `\x7fELF`, Mach-O and its reversed forms, `dex\n`), archives (`PK\x03\x04`, 7z, `Rar!`, gzip, xz, zstd), OLE and `%PDF`;
  - mode `100755` outside `scripts/` and `.claude/hooks/`;
  - files over 512 KB;
  - any symlink.
- `.gitattributes`: `* text=auto eol=lf`; **no Git LFS**. LFS objects are still public and hard to purge.
- Tests build every case in `tmp_path` from a few header bytes. No EICAR, which trips antivirus on dev machines.
- Secrets:
  - `.gitleaks.toml` extends the defaults with **no path allowlist**. `test_gitleaks_config.py` fails if any allowlist is added beyond an explicit reviewed list.
  - `test_gitleaks.py` generates a high-entropy provider-format token in `tmp_path` at runtime, runs the pinned binary with the repo config (`gitleaks dir`), and asserts detection; a clean file must pass. Locally it skips with a message if the binary is missing; in CI a missing binary is a failure.
  - CI also runs gitleaks over full history (`fetch-depth: 0`) on push to `main`.

### 5.5 Hard rule 2 (no artifact parsing in the API) — layered
1. **import-linter `forbidden` contract** on `rex_api` with `include_external_packages = True`, forbidding third-party parsers and archive libraries (`magic`, `lief`, `pefile`, `elftools`, `py7zr`, `rarfile`, `PIL`, `dill`, `jsonpickle`). It follows indirect imports, which closes the route of importing a helper from a shared package. If stdlib modules can't be forbidden this way (the builder verifies), they stay with layer 2.
2. **Semgrep `rex-api-no-artifact-parsing`** on `services/api/**`:
   - process spawning: `subprocess.*`, `os.system`, `os.popen`, `os.exec*`, `os.spawn*`, `os.posix_spawn`, `pty.spawn`, `asyncio.create_subprocess_*`;
   - archives and decompression: `zipfile`, `tarfile`, `shutil.unpack_archive`, `gzip`, `bz2`, `lzma`, `zlib` decompression;
   - unsafe deserialization: `pickle`, `marshal`, `shelve`, `yaml.load` without SafeLoader;
   - `xml.etree` (use defusedxml) and `ctypes`.
3. **Semgrep `rex-no-dynamic-import`** on `services/**` and `packages/**`: `__import__`, `importlib.import_module`, `exec`, `eval`.

Every bypass form is a `ruleid:` fixture, including aliased imports, `from … import` and string-built module names. Run with `semgrep --test`.

Other REX rules, each with `ruleid:` and `ok:` fixtures:
- `rex-no-shell-true`.
- `rex-no-secret-in-logs`: logging, `print` and structlog kwargs where a value or keyword names `password|secret|token|api_key|private_key`, including f-strings and `%` formatting. Stated guarantee: catches obvious leaks, not all of them. #42 adds runtime redaction.
- `rex-no-custom-crypto`: `random.*` used for tokens or keys (use `secrets`); `==` or `!=` on digest or HMAC values (use `hmac.compare_digest`); low-level cipher construction outside an allowlisted module.

### 5.6 Import boundaries (`.importlinter`, generated)
- `scripts/gen_importlinter.py` writes `.importlinter` from the workspace members, listing each package explicitly (import-linter has no wildcards). Contracts:
  - `independence` among service packages;
  - `forbidden`: every `rex_worker_*` → any service;
  - `forbidden`: `rex_contracts`, `rex_shared_config` and `rex_plugin_sdk` → any service or worker;
  - the §5.5 API contract.
- `test_boundaries.py`:
  - runs the generator on a temp tree that uses the real naming scheme, and asserts that `lint-imports` fails on a violating import and passes on a clean tree;
  - asserts the committed `.importlinter` equals the generator's output on the repo.
- The `guards` job runs `lint-imports` only when the generator finds ≥1 member, and logs loudly when it skips. It finds none until 0b adds packages.

### 5.7 Workflow security
- **zizmor** (`--min-severity low`) and **actionlint** are required steps.
- `test_workflows.py` adds REX-specific policy on top of them. For all `uses:` (steps, job-level reusable workflows, `.github/actions/**/action.yml`):
  - full 40-hex SHA with a version comment; `docker://` requires `@sha256:`;
  - triggers `pull_request_target` and `workflow_run` are banned;
  - top-level `permissions: {}`, and job permissions limited to an allowlist per job;
  - `actions/checkout` has `persist-credentials: false`;
  - `runs-on` is `ubuntu-24.04`, never `-latest`;
  - no `${{ … }}` of `github.event.*`, `github.head_ref`, `inputs.*` or `steps.*.outputs.*` inside `run:` or `github-script` `script:` (passing through `env:` is the allowed pattern);
  - no `secrets: inherit`.
  - Each rule has a failing fixture workflow generated in `tmp_path`.
- **harden-runner** (pinned) in every job with `egress-policy: audit`. Moves to `block` with an allowlist in 0b.
- Concurrency: `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, so runs on `main` aren't cancelled.

### 5.8 CI workflows

| Workflow | Trigger | Jobs (all SHA-pinned, `ubuntu-24.04`, harden-runner) |
|---|---|---|
| `ci.yml` | `pull_request` (no `branches:` filter, so stacked PRs run), push `main` | `changes` (dorny/paths-filter **inside** the workflow, never `on.paths`)<br>`guards`: pytest `tests/repo`, `semgrep --test` + REX rules with `--error`, import-linter, binary check, zizmor, actionlint<br>`python`: ruff, pyright, pytest on the 3.13/3.14/3.15 matrix; runs when Python packages change; pytest exit 5 (nothing collected) is allowed only when the job detects no test dirs<br>`ts`: eslint, tsc, tests; runs only when a TS workspace package exists<br>**`ci-ok`** aggregator: `if: always()`, needs all the above, fails unless every result is `success` or `skipped` |
| `security.yml` | `pull_request`, push `main`, weekly | `gitleaks` (binary; full history on push)<br>`dependency-review` (PR; `fail-on-severity: high`, `allow-licenses` = policy list)<br>`osv-vulns` and `osv-licenses` (reusable workflows; fail on high/critical vulns or any non-allowlisted license; **fail if 0 packages scanned**)<br>`codeql` v4: languages **actions** + **python**, javascript-typescript added by guard once TS code exists; `build-mode: none`<br>`semgrep-registry` (`p/python`, `p/typescript`, `p/github-actions`; advisory) |
| `sbom.yml` | push `main` | Syft via anchore/sbom-action → CycloneDX artifact |
| `pr-title.yml` | `pull_request` types opened/edited/synchronize/reopened | conventional title; title is never interpolated into `run:` |
| `scorecard.yml` | push `main`, weekly, `branch_protection_rule` | official steps only; `publish_results: true`; `id-token: write` at job level only |

Pass/fail is independent of SARIF upload. SARIF uploads (`security-events: write`) run only on push or same-repo PRs, since fork PRs get a read-only token.

Dependabot (`dependabot.yml`):
- ecosystems `uv`, `npm` (pnpm), `github-actions`, `pre-commit`;
- `cooldown.default-days: 7`;
- `commit-message.prefix: "chore(deps)"`, which satisfies the PR-title check;
- grouped minor/patch updates.

Failure thresholds and their rationale are documented in `docs/security/ci-policy.md`.

### 5.9 License policy (owner-approved list)
`docs/security/dependency-licenses.md`:
- **Allowlist:** MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, PSF-2.0, 0BSD, CC0-1.0, Unlicense, Zlib, MPL-2.0.
- **Denied:** GPL, AGPL, LGPL as linked dependencies; SSPL; BUSL; unknown.
- SPDX expressions are evaluated properly: `MIT OR GPL-3.0` passes, `MIT AND GPL-3.0` fails.
- **Dev-tool category:** tools not distributed and run only as processes (initially Semgrep CE, LGPL-2.1) are listed by `name@range`, with a reason and an issue link, in `osv-scanner.toml` overrides.
- Analysis tools (Ghidra and the others) are reviewed per adapter issue.
- `test_license_policy.py` asserts the doc's machine-readable block, `osv-scanner.toml` and the dependency-review `allow-licenses` list agree.
- A NOTICE check asserts NOTICE exists with the project attribution. Third-party notices come with images in 0b.

### 5.10 Governance and repo settings (sole maintainer)
- `CODEOWNERS`: `* @affan80` plus explicit security-sensitive paths:
  - auth and authz;
  - evidence, permits, crypto;
  - workers and `infrastructure/pc2-workers`;
  - `infrastructure/pc3-security-gateway`;
  - `workers/validation` and `packages/plugin-sdk`;
  - `.github/`, `.claude/`, `semgrep/`, `.importlinter`, `.gitleaks.toml`, `osv-scanner.toml`, `docs/security/`.
  - With one maintainer it routes review requests; it does not block merges. The real protection is required checks plus workflow policy. The settings doc says this plainly.
- Templates (PR, bug, feature, ADR, security), `SECURITY.md` (private vulnerability reporting), and a pre-commit `commit-msg` conventional check.
- `docs/operations/repo-settings.md` holds the exact `gh api` calls:
  - **Ruleset on `~DEFAULT_BRANCH`:**
    - `pull_request` with `required_approving_review_count: 0`, `require_code_owner_review: false`, `allowed_merge_methods: ["squash"]`;
    - `required_linear_history`, `non_fast_forward`, `deletion`;
    - `required_signatures`: squash merges made by GitHub are signed;
    - `required_status_checks` with `integration_id: 15368` (GitHub Actions) and `strict: true`;
    - a code-scanning rule (CodeQL, high or higher).
    - **No bypass actors.** Break-glass: temporarily disable the ruleset, which is visible in the audit log.
  - Repo security: enable vulnerability alerts, then Dependabot security updates, private vulnerability reporting, and non-provider secret patterns.
  - Actions settings:
    - default `GITHUB_TOKEN` read-only, and Actions may not create or approve PRs;
    - only allowed actions, with **SHA pinning required**;
    - fork-PR workflows need approval for all outside contributors.
  - A `v*` tag ruleset is staged for #31.
- Accepted Scorecard limits for a solo repo, recorded: Code-Review, Contributors, Maintained (first 90 days), Fuzzing (0b+), Signed-Releases (#31). Branch-Protection may show `?` without an admin PAT. We don't add one.

### 5.11 Docs
- ADR template, `docs/adr/README.md` index, ADR-0001 (record decisions), ADR-0002 (§4.1, Accepted).
- `docs/architecture/overview.md`: C4 context and container diagrams in Mermaid, showing PC 1/2/3; open decisions appear as labelled placeholders with their issue numbers.
- `docs/security/threat-model.md` v1: STRIDE per trust boundary (user↔API, API↔storage, PC1↔PC2, PC2↔PC3↔internet, platform↔AI providers, agents↔repo, CI↔third-party actions). Each threat maps to a hard rule and a planned `tests/security/` location.

## 6. Delivery: stacked PRs (owner decision), hardened

Order:
1. Layout, LICENSE/NOTICE, docs base, ADR-0001/0002, CLAUDE.md, workspace tooling.
2. Workflow policy + `ci.yml` (guards, Semgrep rules, boundaries, binary check, zizmor/actionlint, `ci-ok`).
3. Agent guardrails (`.claude/`, sandbox, hook, tests).
4. Security scanning (`security.yml`, gitleaks, osv, dependency review, CodeQL, SBOM, Scorecard, Dependabot).
5. Governance (CODEOWNERS, templates, SECURITY.md, PR title, pre-commit, repo-settings doc).
6. Threat model v1 + architecture overview.

Rules:
- Merge strictly one at a time, squash. Retarget the next PR to `main` and rebase it before its review.
- Workflows trigger on `pull_request` with no branch filter, so stacked PRs are checked too.
- After PR 1 merges: apply a **minimal ruleset** (PR required, no force push, no deletion, linear history, squash only).
- After each later PR merges: add its checks as required (`ci-ok` after PR 2; security jobs after PR 4) and apply that PR's repo settings.
- After PR 5: the full settings from §5.10.

## 7. Left to the builder
File formatting; ruff/eslint details beyond §5.2; README wording; exact SHAs and checksums (resolved at write time from official releases); Dependabot group names.

## 8. Owner decisions
Already decided (2026-11-27):
1. Workspace tooling: uv + pnpm + just.
2. The license list.
3. `brew install just gitleaks`.
4. Apply GitHub repo settings via `gh api`.
5. Plugins stay personal.
6. Stacked PRs.

**New, needed for v2:**
- **A. Timing of repo settings.** Apply a minimal ruleset after PR 1 and add required checks as each PR merges (§6), instead of applying everything after the last PR.
- **B. Commit Claude Code sandbox + deny + hook settings (§5.3).** They apply to every Claude Code session in this repo, including this one once merged. Shell commands then run sandboxed with network limited to the listed dev hosts, and agents can't edit `.claude/**`.
- **C. Upgrade the host toolchain to current:** uv 0.11 → 0.13.10 (brew), Node 22 → 26 LTS (brew), pnpm 10 → 12 (pinned install).
- **D. Solo-maintainer ruleset** with 0 required approvals and no bypass actors (§5.10). Code-owner review can't be enforced for a sole maintainer; required checks are the real gate.

My calls, which you can override: Python dev default 3.15 with floor 3.13 and a 3.13–3.15 matrix; `rex_<dir>` naming; TS pinned to 6.0.x; SHA pins instead of `actions.lock` for now; osv-scanner for licenses; samples kept outside the repo as password-protected archives; the 0b deferrals in the header.
