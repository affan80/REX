# Phase 0a: Repo Foundation and Guardrails — Design

Status: Draft for owner approval
Date: 2026-11-27
Issues: #1 (ADR workspace), #18–#26, #32–#33, #35–#40. The PR uses "Refs #N" and closes only issues whose acceptance criteria are fully met; partially covered issues get a comment listing what moves to 0b.
Follow-up (Phase 0b, separate design): #41 contracts, #42 shared config + log redaction, #43 Compose stack, #19/#20 full language gates once real code exists, #28 images, #29 contracts CI, #31 release workflow (depends on images), #34 `.env.example` + compose recipes, Dependabot `docker` ecosystem and image license/SBOM coverage (#22–#24, once Dockerfiles exist), TS boundary check via dependency-cruiser (#26, once TS packages exist), MCP for Postgres/Playwright (#35).

## 1. Intent

REX handles hostile artifacts and lives in a **public** GitHub repo. Before any product code exists, the repo itself must make the REX hard rules and working rules hard to break by accident: by a person, by CI, or by an AI agent working in the repo. Phase 0a builds that guardrail layer so every later PR lands inside it.

Success: a PR that plants a fake secret, adds a forbidden cross-service import, uses an unpinned GitHub Action, adds a disallowed-license dependency, or puts artifact-parsing code in `services/api` fails CI; an agent in this repo cannot read or execute files from the local sample directory.

## 2. Goals, non-goals, anti-goals

Goals
- Monorepo layout from CLAUDE.md, with uv (Python) + pnpm (TS) workspaces and a `justfile` as the single entry point.
- Docs base: LICENSE/NOTICE (Apache-2.0), ADR template, ADR-0001 (record decisions), ADR-0002 (workspace tooling, Accepted), CONTRIBUTING, SECURITY, threat model v1.
- CLAUDE.md + `.claude/settings.json` + a guard hook for agents.
- CI baseline: workflow policy, Python + TS quality jobs, secret scan, dependency review + Dependabot, license compliance, SBOM, CodeQL, Semgrep with REX custom rules, import-boundary check, PR title check, OpenSSF Scorecard.
- Pre-commit mirroring the fast CI checks.

Non-goals
- No product code (no API, workers, adapters, DB). Packages are created only when they have code (YAGNI): service/worker dirs get a README only.
- No Compose stack, contracts codegen, container images (Phase 0b).
- No decisions on any other open ADR (#2–#17).

Anti-goals (failure even if it "works")
- Any real malware sample, or any real secret, ever committed to the repo.
- CI that passes because a check is silently skipped (e.g. a guard with no fixture proving it fires).
- Unpinned third-party actions or workflows with write permissions by default.
- Guard config that blocks normal development so badly people disable it.

## 3. Constraints

- Hard rules 1–14 in CLAUDE.md; esp. 9 (secrets), 11 (no custom crypto), 13 (versioned contracts), 14 (license review).
- Public repo: CodeQL, dependency review, secret scanning are free; push protection is already enabled.
- Host has uv 0.11, pnpm 10, Node 22, Python 3.15, Docker 29. Missing: just, gitleaks, pre-commit, semgrep.
- Every guard ships with a fixture/test proving it fires (working rule: security change ⇒ regression test).

## 4. Approaches considered

Workspace tooling (ADR #1) — **decided by owner: uv + pnpm + just.**
- uv workspaces + pnpm workspaces + justfile — simple, fast, permissive licenses; no cross-language cache (CI uses path filters). **Chosen.**
- Nx + Python plugin — affected-graph and caching across languages; heavier, Python via community plugin.
- Pants — hermetic, strong Python; steep learning curve.

Scope split — **my call:** Phase 0a (guardrails, this doc) then Phase 0b (contracts, config/redaction, Compose). Why: 0b's redaction work is security-sensitive and needs its own approval; one PR per concern.

How guards are proven — **my call:** a Python test suite under `tests/repo/` (pytest) that exercises each guard against fixtures, run in CI and via `just test`. Alternative (CI-only fixture jobs) rejected: harder to run locally, easy to silently skip.

## 5. Design

### 5.1 Layout
All directories from CLAUDE.md are created. Dirs without code get a `README.md` stating purpose and owning phase/issue. Additional root files:

```
.claude/settings.json, .claude/hooks/guard_samples.py
.github/{workflows/*, CODEOWNERS, dependabot.yml, pull_request_template.md, ISSUE_TEMPLATE/*}
.gitignore, .gitattributes, .editorconfig, .pre-commit-config.yaml, .gitleaks.toml
.python-version, pyproject.toml (uv workspace root), uv.lock
package.json, pnpm-workspace.yaml, pnpm-lock.yaml, tsconfig.base.json, eslint.config.js
justfile, CLAUDE.md, CONTRIBUTING.md, SECURITY.md, LICENSE, NOTICE
semgrep/rules/*.yaml + semgrep/tests/*
.importlinter
tests/repo/*  (guard tests)
docs/adr/{0000-template.md,0001-record-architecture-decisions.md,0002-monorepo-workspace-tooling.md,README.md}
docs/security/{threat-model.md,dependency-licenses.md}
docs/architecture/overview.md
```

### 5.1a Package naming (my call)
Every Python workspace member uses src layout with import name `rex_<dir>` (hyphens → underscores): `services/api/src/rex_api`, `services/ai-gateway/src/rex_ai_gateway`, `workers/analysis/src/rex_worker_analysis`, `packages/contracts/src/rex_contracts`, `packages/shared-config/src/rex_shared_config`. Distribution names use hyphens (`rex-api`). TS packages are `@rex/<dir>`. The import-linter config in §5.6 is written against these names, and `tests/repo/test_boundaries.py` builds its temp tree with the same names so the test exercises the real config.

### 5.2 Toolchain
- Python: `.python-version` = 3.13, `requires-python = ">=3.13"` (my call: broad tool support; 3.15 is too new for some deps). uv workspace members glob: `services/*`, `workers/*`, `packages/*` — only dirs with a `pyproject.toml` join.
- Root dev dependency group: pytest, ruff, pyright, import-linter, pyyaml, pip-licenses.
- TS: Node 22, pnpm 10 (`packageManager` field), `pnpm-workspace.yaml` covers `apps/*`, `packages/*`. Root dev deps: typescript, eslint, typescript-eslint, license-checker-rseidelsohn.
- `justfile` recipes: `setup`, `lint`, `typecheck`, `test`, `guards`, `licenses`, `precommit`.
- semgrep and pre-commit run via `uvx` at pinned versions (no host install). gitleaks via its pre-commit hook / official action. `just` itself needs a host install (§7).

### 5.3 Agent guardrails
- `CLAUDE.md` = the REX project context verbatim, plus a "Repo conventions" section (just recipes, where samples live, ADR process).
- Real samples live only in `~/.rex-samples/` or repo-local `.rex-samples/` (git-ignored). `.gitignore` also ignores `*.quarantine`, `samples/`, `quarantine/`.
- `.claude/settings.json`: `permissions.deny` for `Read`/`Edit` of `.rex-samples/**`, `**/quarantine/**`, `.env*`. **No plugins declared in repo settings** (owner decision): ponytail and superpowers stay personal; CONTRIBUTING documents them as optional, with install steps, "leave ponytail's webhook empty", and "CLAUDE.md rules override plugin defaults".
- `.claude/hooks/guard_samples.py` as a PreToolUse hook on Bash: blocks commands that reference sample/quarantine paths, or execute (`./x`, `chmod +x`, `bash x`, `python x`) files in them. Tested by `tests/repo/test_guard_samples.py` (block + allow cases).
- `.mcp.json`: not added in 0a (GitHub MCP is user-level and its auth is broken; Postgres/Playwright arrive with 0b/Phase 4). Tracked in #35.

### 5.4 CI workflows (all: actions pinned by full SHA, top-level `permissions: {}`, per-job least privilege, concurrency cancel)
| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | PR, push main | `guards` (pytest tests/repo, semgrep --test, import-linter), `python` (ruff, pyright, pytest; path-filtered), `ts` (eslint, tsc, test `--if-present`; path-filtered), `licenses` |
| `security.yml` | PR, push main, weekly | gitleaks, dependency-review (PR only, `fail-on-severity: high`), osv-scanner over `uv.lock` + `pnpm-lock.yaml` (fail on high/critical), CodeQL (python, javascript-typescript), semgrep (REX rules + `p/default`) → SARIF. Failure thresholds documented in `docs/security/ci-policy.md`. |
| `sbom.yml` | push main, release | Syft (anchore/sbom-action) CycloneDX → artifact |
| `pr-title.yml` | PR | conventional-commit title check |
| `scorecard.yml` | weekly, push main | OpenSSF Scorecard → SARIF |
| `dependabot.yml` | — | pip(uv), npm, github-actions; weekly |

`tests/repo/test_workflows.py` enforces the policy on every workflow file: every `uses:` pinned to a 40-hex SHA (local `./` actions exempt), top-level `permissions` present, no `pull_request_target`, no `${{ github.event.* }}` interpolated directly in `run:`.

### 5.5 REX custom Semgrep rules (each with `ruleid:`/`ok:` fixtures, run by `semgrep --test`)
- `rex-api-no-artifact-parsing` (rule 2): in `services/api/**`, flag `subprocess.*`, `os.system`, `zipfile`, `tarfile`, `py7zr`, `rarfile`, `magic`, `lief`, `pefile`, `elftools`, `pickle.load(s)`, `yaml.load` without SafeLoader.
- `rex-no-custom-crypto` (rule 11): flag imports of low-level primitives (`cryptography.hazmat.primitives.ciphers`, `Crypto.Cipher`, `hashlib` used with `hmac` hand-rolled comparisons via `==` on digests) — use vetted high-level APIs.
- `rex-no-secret-in-logs` (rule 9): logging calls whose args name `password|secret|token|api_key|private_key`.
- `rex-no-shell-true` : `subprocess.*(..., shell=True)` anywhere.

### 5.6 Import boundaries (`.importlinter`)
- Independence contract: `rex_api`, `rex_scheduler`, `rex_ai_gateway`, `rex_integration_service` may not import each other.
- Forbidden: `rex_worker_*` may not import any service package (workers never hold control-plane code/credentials).
- `rex_contracts` may not import any service or worker package (it is the shared leaf).
- Contracts list only packages that exist; `scripts/gen_importlinter.py` regenerates `.importlinter` from the workspace members, and `tests/repo/test_boundaries.py` also asserts the committed `.importlinter` matches the generator output (so a new service can't be silently left out).
Since no packages exist yet, `tests/repo/test_boundaries.py` builds a temp tree with a violating import and asserts `lint-imports` with the repo config fails, and a clean tree passes.

### 5.7 Secrets
- `.gitleaks.toml` extends defaults; allowlist only `tests/repo/fixtures/secrets/**` which contains *fake* keys.
- `tests/repo/test_gitleaks.py` runs gitleaks (skips with a clear message locally if the binary is absent; CI installs it, and the CI job fails if it's absent) against a fixture with a fake AWS-style key ⇒ detected, against a clean file ⇒ clean.

### 5.8 Licenses
- `docs/security/dependency-licenses.md`: allowlist + denylist + exception process. Allowlist (**approved by owner 2026-11-27**): MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, PSF-2.0, 0BSD, CC0-1.0, Unlicense, Zlib, MPL-2.0 (file-level copyleft). Denied by default: GPL-*, AGPL-*, LGPL-* (as dependencies; analysis tools run as separate processes are reviewed per adapter issue), SSPL, BUSL, unknown.
- `scripts/check_licenses.py` reads the allowlist from that doc's machine block and checks `pip-licenses --format=json` and the pnpm license-checker JSON. `tests/repo/test_licenses.py` feeds it fixture JSON with an allowed and a GPL entry.

### 5.9 Governance files
- `CODEOWNERS`: `* @affan80`; explicit entries for security-sensitive paths: auth/authz (`services/api/**/auth*`, `services/api/**/authz*`), crypto/evidence/permits (`**/evidence/`, `**/permits/`, `**/crypto/`), sandbox and workers (`workers/`, `infrastructure/pc2-workers/`), network gateway (`infrastructure/pc3-security-gateway/`), validation (`workers/validation/`), plugin SDK (`packages/plugin-sdk/`), and repo guardrails (`.github/`, `.claude/`, `semgrep/`, `.importlinter`, `.gitleaks.toml`, `docs/security/`).
- Pre-commit includes a `commit-msg` conventional-commit check, in addition to the PR-title workflow.
- PR template: plan, tests added, docs/ADR updated, security-sensitive? risks.
- Issue templates: bug, feature, ADR, security (pointing to private reporting).
- `SECURITY.md`: report privately via GitHub private vulnerability reporting.
- Repo settings (ruleset on `main`, required checks, Dependabot security updates, private vulnerability reporting) are applied with `gh api` **only after owner approval** (§7); the exact commands live in `docs/operations/repo-settings.md`.

### 5.10 Threat model v1 (`docs/security/threat-model.md`)
STRIDE per trust boundary: user↔API, API↔storage, control plane↔workers (PC1↔PC2), workers↔gateway↔internet (PC2↔PC3), platform↔AI providers, agents↔repo. Each threat maps to a hard rule and a planned test location in `tests/security/`. Open decisions referenced by ADR issue number, not invented.

### 5.11 Docs specifics
- `CLAUDE.md` content source: the REX project context the owner provided (hard rules 1–14 numbered as given; layout; stack; build order; unresolved decisions; working rules), copied verbatim, then a "Repo conventions" section appended.
- `docs/architecture/overview.md` includes C4 context + container diagrams in Mermaid (renders on GitHub, no binary assets), showing PC 1/2/3 and open decisions as labelled placeholders.
- Ruleset commands in `docs/operations/repo-settings.md` include linear history.

## 6. Left to the builder
File-level formatting, ruff rule selection beyond defaults + `S` (bandit) + `B`, ESLint config details, README wording, exact SHAs (resolved at write time from the official action repos).

## 7. Owner decisions (2026-11-27)
1. Dependency-license allowlist/denylist in §5.8: **approved as proposed**.
2. `brew install just gitleaks` on the dev machine: **approved**.
3. Apply GitHub repo settings via `gh api` after the last 0a PR merges (ruleset on `main`: PR required, required checks, linear history, no force push; Dependabot security updates; private vulnerability reporting): **approved**.
4. Plugins: **kept personal**, not declared in repo settings (§5.3).
5. Delivery: **stacked PRs, one per concern**, in this order so each later PR is checked by the guards before it:
   1. Layout + LICENSE/NOTICE + docs base + ADR-0001/0002 + CLAUDE.md + workspace tooling (uv/pnpm/just)
   2. Workflow policy + `ci.yml` guards job (workflow test, semgrep rules, import boundaries, licenses)
   3. Agent guardrails (`.claude/` settings + sample guard hook)
   4. Security scanning (`security.yml`, gitleaks config, osv-scanner, CodeQL, SBOM, Scorecard, Dependabot)
   5. Governance (CODEOWNERS, templates, SECURITY.md, PR-title check, pre-commit, repo-settings doc)
   6. Threat model v1 + architecture overview

My calls (owner may override): Python 3.13 floor; `rex_<dir>` src-layout package naming (§5.1a); tests in `tests/repo/` prove every guard; CODEOWNERS owner `@affan80` (sole collaborator); the gap items in the header deferred to 0b.
