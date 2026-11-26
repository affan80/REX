---
status: accepted
date: 2026-11-27
decision-makers: affan80
issue: "#1"
---

# Use uv workspaces, pnpm workspaces and a justfile for the REX monorepo

## Context and Problem Statement

REX is one repository holding Python services, workers and packages (FastAPI, analysis workers, SDK, tool adapters) and TypeScript code (Next.js web app, TypeScript SDK), plus infrastructure and docs. We need one way to install, lock, build, test and version both languages, which the CI baseline (#18), the scaffold (#37) and the dev environment (#34) all build on. Issue: #1.

## Decision Drivers

* **Hard rule 14 / supply chain:** every tool must be on the licence allowlist, and dependencies must be locked and reproducible (lockfiles, hashes, release cooldowns).
* **Hard rule 13:** packages and contracts are versioned per package.
* **Service boundaries:** no service imports another service's private code, so each service or worker is its own package with explicit dependencies.
* **Sole maintainer:** low learning curve and few moving parts to trust and keep updated.
* **Speed:** fast installs locally and in CI.
* **Latest stable tools**, checked against official release notes.

## Considered Options

* uv workspaces (Python) + pnpm workspaces (TypeScript) + a `justfile` task runner
* Nx (with a Python plugin) for both languages
* Pants for both languages
* moon for both languages

## Decision Outcome

Chosen option: "uv workspaces + pnpm workspaces + a `justfile`", decided by the owner on 2026-11-27. Each language gets its own native, fast, widely used workspace tool with a lockfile, and one small `justfile` gives humans, agents and CI the same entry points. It has the fewest moving parts to trust, and every piece is permissively licensed.

### Consequences

* Good, because `uv.lock` and `pnpm-lock.yaml` lock every dependency (including transitive ones and tool dependencies), with release cooldowns: `exclude-newer` in uv and `minimumReleaseAge` in pnpm.
* Good, because each service, worker and package is its own workspace member with explicit dependencies. That makes import boundaries enforceable (#26).
* Good, because the tools are fast and their official GitHub Actions (`astral-sh/setup-uv`, `pnpm/action-setup`) are maintained by the tool authors.
* Bad, because there is no cross-language task graph or build cache. CI uses change detection inside the workflow to skip unaffected jobs instead.
* Bad, because the two languages are upgraded separately: two lockfiles and two Dependabot ecosystems.
* Neutral, because `just` is a separate binary. CI installs it pinned; contributors install it locally (Homebrew or the `rust-just` PyPI package).

### Confirmation

* Scaffold (#37): the root `pyproject.toml` declares the uv workspace and `pnpm-workspace.yaml` declares the pnpm workspace. CI runs `uv sync --locked` and `pnpm install --frozen-lockfile`, which fail if a lockfile is stale.
* Dev environment (#34): the `justfile` holds the shared recipes (`setup`, `lint`, `typecheck`, `test`, `guards`), and CI calls those recipes instead of duplicating commands.
* Any change of workspace tooling requires a new ADR that supersedes this one.

## Pros and Cons of the Options

### uv workspaces + pnpm workspaces + justfile

* Good, because each tool is the native, mainstream choice for its language, with lockfiles and supply-chain settings built in.
* Good, because the learning curve is small and the docs are first-party.
* Good, because the official CI actions are maintained by the tool authors.
* Bad, because there is no shared build cache or "affected" graph across languages.
* Licence: uv `MIT OR Apache-2.0`; pnpm `MIT`; just `CC0-1.0`. All are allowed.
* Security: lockfiles with hashes, `uv sync --locked`, `pnpm install --frozen-lockfile`, pnpm's blocked lifecycle scripts by default (`allowBuilds`), and release cooldowns.
* Versions checked: uv 0.13.10 (2026-11-24), pnpm 12.23.0 (2026-11-22), just 1.59.0 (2026-10-15).

### Nx (with a Python plugin)

* Good, because it has a cross-language task graph, "affected" builds and optional remote caching.
* Bad, because Python support comes from a community plugin, which is another large dependency to trust and keep compatible.
* Bad, because there is more configuration and conceptual overhead for a sole maintainer.
* Licence: `MIT`. Allowed. Remote caching would be an external service to review separately.
* Security: a big plugin and dependency surface. Remote cache artifacts would need trust controls.
* Version checked: 24.0.7 (2026-11-25).

### Pants

* Good, because it gives hermetic builds, fine-grained dependency inference and strong Python support.
* Bad, because it has the steepest learning curve and slower onboarding for contributors and agents.
* Bad, because it brings its own lockfile and resolve concepts that differ from standard Python tooling.
* Licence: `Apache-2.0`. Allowed.
* Security: strong hermeticity. The Pants runtime itself is another large toolchain to trust.
* Version checked: 2.32.2 (2026-11-01).

### moon

* Good, because it is a polyglot task runner with project graphs and caching, and it is lighter than Nx.
* Bad, because it is smaller and less widespread, and its Python support is less mature than uv's native workspaces.
* Bad, because it would still sit on top of uv and pnpm, adding a layer rather than replacing one.
* Licence: `MIT`. Allowed.
* Security: one more toolchain and binary to trust.
* Version checked: 2.6.6 (2026-11-24).

## More Information

* Sources (checked 2026-11-27): GitHub releases and licence files of astral-sh/uv, pnpm/pnpm, casey/just, nrwl/nx, pantsbuild/pants and moonrepo/moon.
* Follow-up issues: #37 (scaffold), #34 (dev environment), #18 (CI baseline), #44 (Phase 0 gate).
* Revisit if CI time grows enough that a cross-language build cache would pay for itself. That needs a new ADR.
