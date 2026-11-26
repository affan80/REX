# Phase 0a: Repo Foundation and Guardrails — Design (v2)

Status: **Approved by owner 2026-11-27.** Revised after:
- a builder check;
- an adversarial security review;
- a verification of the Claude Code docs;
- latest-version research (versions verified 2026-11-27).

v3 adds the owner's delivery decisions (the `dev` branch, one issue per PR) and clarifies how tests work (§4.2).
Issues: #1 (ADR workspace), #18–#26, #32–#40, plus a new issue for blocking binaries and samples in git (§5.4). One issue = one PR into `dev` (§6). An issue is closed only when all its acceptance criteria are met. A partially covered issue gets a comment listing what moved to 0b and stays open.
Phase 0b (separate design): #41 contracts, #42 shared config + log redaction, #43 Compose, #27 images, #28 contracts CI, #31 release workflow. Also the remainders of:
- #20: `next build`, once apps/web exists;
- #22/#23/#24: Docker ecosystem, image licenses and SBOMs, NOTICE generation, SBOM release attachment + attestation;
- #26: TS boundary check;
- #34: `.env.example`, compose recipes;
- #35: MCP servers for Postgres and Playwright.

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
Every guard is a **checker** (a script, hook, Semgrep rule or import contract) proven in two halves:
1. A pytest suite in `tests/repo/` (or `semgrep --test` fixtures) runs the real checker against fixtures **generated at test time in `tmp_path`**, and asserts exit codes and findings. The test is watched failing first.
2. CI runs the same checker over the real repo.

Binary or secret-shaped fixtures are never committed.

Configuration files get no unit tests that search their text. These include dependabot.yml, pnpm-workspace.yaml, pyproject settings, CODEOWNERS and templates. Each is validated by the tool that reads it: `uv lock --check`, `pnpm install --frozen-lockfile`, actionlint, check-jsonschema schemas, GitHub's CODEOWNERS error API, or reading settings back from the API.

Prose for humans gets no tests: CONTRIBUTING, ADRs, the threat model.

Rejected:
- CI-only fixture jobs: hard to run locally, easy to skip silently.
- Config tests that search for text: they pass as long as the file says what it says, whatever it does.

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
- Tests (`tests/repo/test_guard_samples.py`) run the real script as a subprocess with real hook JSON for each tool.
  - They assert exit 2 on block cases: a direct path, `~`, `$HOME`, a symlink, a glob, `..` traversal, a Grep path, malformed JSON, and **different letter case**. macOS APFS is case-insensitive, so `~/.REX-Samples/x` is the same directory.
  - They assert exit 0 on normal cases, including near-miss strings that only mention the words (`echo quarantine-policy`, `git commit -m "docs: samples guide"`).
- `scripts/check_agent_policy.py` validates `.claude/settings.json` against REX's agent policy:
  - the hook is wired to an existing script with the required matcher;
  - deny rules cover the sample and secret paths;
  - the sandbox is enabled, with `failIfUnavailable` and `allowUnsandboxedCommands: false`;
  - bypass mode is disabled.

  It is tested with fixture settings files, each missing one piece and expected to fail, and it runs in CI on the real file.
- Plugins stay personal (owner decision). CONTRIBUTING documents superpowers and ponytail as optional, with "leave ponytail's webhook empty".
- `.gitignore` adds `.claude/settings.local.json`, `CLAUDE.local.md`, `.env`, `.env.local`, `.env.*.local`, `.rex-samples/`, `quarantine/`.
- No `.mcp.json` in 0a (#35 → 0b).

### 5.4 Preventing samples, binaries and secrets in git
- `scripts/check_no_binaries.py`, run as a pre-commit hook **and** as a CI step over `git diff --name-only <base>...HEAD`, so `--no-verify` doesn't skip it. It rejects:
  - files whose magic bytes match executables (`MZ`, `\x7fELF`, Mach-O and its reversed forms, `dex\n`), archives (`PK\x03\x04`, 7z, `Rar!`, gzip, xz, zstd), OLE and `%PDF`;
  - mode `100755` outside `scripts/` and `.claude/hooks/`;
  - files over 512 KB (the lockfiles `uv.lock` and `pnpm-lock.yaml` are exempt);
  - any symlink.
- `.gitattributes`: `* text=auto eol=lf`; **no Git LFS**. LFS objects are still public and hard to purge.
- Tests build every case in `tmp_path` from a few header bytes. No EICAR, which trips antivirus on dev machines.
- Secrets:
  - `.gitleaks.toml` extends the defaults with **no path allowlist**. The detection test places the generated token at several representative paths (`tests/…`, `docs/…`, `scripts/…`, the repo root) and requires detection at each, so a later allowlist that hides any of them fails the test.
  - `test_gitleaks.py` generates a high-entropy provider-format token in `tmp_path` at runtime, runs the pinned binary with the repo config (`gitleaks dir`), and asserts detection; a clean file must pass. Locally it skips with a message if the binary is missing; in CI a missing binary is a failure.
  - CI also runs gitleaks over full history (`fetch-depth: 0`) on push to `dev` and `main`.

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
- Concurrency: `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, so runs on `dev` and `main` aren't cancelled.

### 5.8 CI workflows

| Workflow | Trigger | Jobs (all SHA-pinned, `ubuntu-24.04`, harden-runner) |
|---|---|---|
| `ci.yml` | `pull_request` (no `branches:` filter), push `dev`/`main` | `changes` (dorny/paths-filter **inside** the workflow, never `on.paths`)<br>`guards`: pytest `tests/repo`, `semgrep --test` + REX rules with `--error`, import-linter, binary check, zizmor, actionlint<br>`python`: ruff, pyright, pytest on the 3.13/3.14/3.15 matrix; runs when Python packages change; pytest exit 5 (nothing collected) is allowed only when the job detects no test dirs<br>`ts`: eslint, tsc, tests; runs only when a TS workspace package exists<br>`release-source`: on PRs into `main`, fails unless the head branch is `dev`<br>**`ci-ok`** aggregator: `if: always()`, needs all the above, fails unless every result is `success` or `skipped` |
| `security.yml` | `pull_request`, push `dev`/`main`, weekly | `gitleaks` (binary; full history on push)<br>`dependency-review` (PR; `fail-on-severity: high`, `allow-licenses` = policy list)<br>`osv-vulns` and `osv-licenses` (reusable workflows; fail on high/critical vulns or any non-allowlisted license; **fail if 0 packages scanned**)<br>`codeql` v4: languages **actions** + **python**, javascript-typescript added by guard once TS code exists; `build-mode: none`<br>`semgrep-registry` (`p/python`, `p/typescript`, `p/github-actions`; advisory)<br>**`security-ok`** aggregator (same rule as `ci-ok`) |
| `sbom.yml` | push `dev` | Syft via anchore/sbom-action → CycloneDX artifact |
| `pr-title.yml` | `pull_request` types opened/edited/synchronize/reopened | conventional title; title is never interpolated into `run:` |
| `scorecard.yml` | push `dev` (default branch), weekly, `branch_protection_rule` | official steps only; `publish_results: true`; `id-token: write` at job level only |

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
- **Single source of truth:** the allowlist and the dev-tool exceptions live in `.github/dependency-review-config.yml` (`allow-licenses`, `allow-dependencies-licenses`), which dependency-review reads directly.
  - `scripts/license_policy.py` derives the osv-scanner `--licenses` argument from that file.
  - It also checks that `osv-scanner.toml` exempts exactly the same packages.
  - It is tested with fixture configs and runs in CI.
- **Dev-tool category:** tools that are not distributed and only run as processes are listed by package URL, with a reason and an issue link. Initially this is Semgrep CE (LGPL-2.1).
- Analysis tools (Ghidra and the others) are reviewed per adapter issue.
- NOTICE stays the project attribution in 0a. Generating third-party notices comes with images in 0b, so #23 stays open for it.

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
  - **Branch model:** `dev` is the default and integration branch. `main` is the release branch.
  - **Ruleset `dev` (`~DEFAULT_BRANCH`):**
    - `pull_request` with `required_approving_review_count: 0`, `require_code_owner_review: false`, `allowed_merge_methods: ["squash"]`;
    - `required_linear_history`, `non_fast_forward`, `deletion`;
    - `required_signatures`: squash merges made by GitHub are signed;
    - `required_status_checks` (`ci-ok`, `security-ok`, `pr-title`) with `integration_id: 15368` (GitHub Actions) and `strict: true`;
    - a code-scanning rule (CodeQL, high or higher).
  - **Ruleset `main` (`refs/heads/main`):** the same as `dev`, with two differences:
    - `allowed_merge_methods: ["merge"]`, with no linear-history rule. That keeps `dev` an ancestor of `main`, so release PRs never conflict.
    - Rulesets can't restrict the source branch, so a `release-source` job in `ci.yml` fails any PR into `main` whose head isn't `dev`.
  - **No bypass actors** on either ruleset. Break-glass: temporarily disable the ruleset, which shows in the audit log.
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

## 6. Delivery: one issue = one PR into `dev` (owner decision, 2026-11-27)

**Bootstrap:**
1. Create `dev` from `main` and make it the default branch.
2. Merge this design and its plan into `dev` as the first PR.
3. Apply the minimal rulesets:
   - both branches: PR required, no force push, no deletion;
   - `dev`: squash only, linear history;
   - `main`: merge commits only.

**Order:** contribution rules first (#39: CONTRIBUTING, ADR process, architecture overview), then #38, #1, #40, #37, #34, #18, the new binary-blocking issue, #19, #20, #26, #25, #21, #22, #23, #24, #33, #35, #36, #32. Phase 0a ends with a release PR from `dev` to `main`, which the owner merges.

**Per-issue lifecycle** (also written into CONTRIBUTING):
1. **Plan before code.** Re-read the issue and the latest official docs for every tool it touches (versions, flags, schemas). Then post the issue's plan as a comment: files, tests, how each acceptance criterion is met, and anything deferred.
2. **Branch** `<type>/<issue>-<slug>` from the latest `origin/dev`.
3. **TDD.** Every checker's test is written first and watched failing.
4. **Open the PR into `dev`.** Title it as a conventional commit, put `Refs #N` in the body, and map each acceptance criterion to its evidence (a test, a CI run, or an API read-back).
5. **Review and CI.** A fresh reviewer checks the diff, and all required checks must be green.
6. **Squash merge.** Then apply any repo settings the issue owns, such as new required checks, and read them back.
7. **Close the issue** only if every acceptance criterion is met, with a comment linking the PR and the evidence. Otherwise, comment what moved to 0b and leave the issue open.

**Required checks** are added as their workflows land: `ci-ok` after #18, `security-ok` after the first security job (#25), and `pr-title` after #32.

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

Decided for v2 (2026-11-27):
- **A. Repo-settings timing: approved.** A minimal ruleset goes on after PR 1, and required checks are added as each PR merges (§6).
- **B. Committed Claude Code sandbox + deny rules + fail-closed hook (§5.3): approved.** This includes `Edit(.claude/**)` denied to agents.
- **C. Host toolchain upgrade: approved.** uv → 0.13.10 and Node → 26 LTS via Homebrew; pnpm → 12 via a pinned install.
- **D. Solo-maintainer ruleset: approved.** 0 required approvals, no bypass actors, required checks as the gate (§5.10).

My calls, which you can override: Python dev default 3.15 with floor 3.13 and a 3.13–3.15 matrix; `rex_<dir>` naming; TS pinned to 6.0.x; SHA pins instead of `actions.lock` for now; osv-scanner for licenses; samples kept outside the repo as password-protected archives; the 0b deferrals in the header.

Decided (2026-11-27, second round):
- **E. Branch model:** every PR targets `dev`. `main` is the release branch.
- **F. One issue at a time, one PR each.** Each issue is planned in detail before any code, including a fresh check of the latest official docs. It is closed only when all its acceptance criteria are done.
- **G. Contribution rules first:** #39 is the first issue.

My calls for this round, which the owner may override:
- `dev` becomes the default branch, because Dependabot, issue templates, scheduled scans and closing keywords all act on the default branch.
- `main` accepts only merge commits from `dev`.
- A new issue tracks blocking binaries and samples in git.
- Config files are validated by the tools that read them, not by unit tests that search their text.
