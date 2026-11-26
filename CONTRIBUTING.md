# Contributing to REX

REX handles hostile artifacts (malware, firmware, exploits) in a **public** repository. These rules keep that safe and keep the history reviewable. They apply to everyone: maintainers, outside contributors and AI agents.

The project's hard rules (untrusted input, deny-by-default, evidence over AI claims, no secrets, no cross-project leakage, and the rest) are in `CLAUDE.md` (added with #35) and win over anything here.

## 1. Branches

| Branch | Purpose | How it changes |
|---|---|---|
| `dev` | **Default branch.** All work integrates here. | Pull requests only. **Squash merge**. Linear history. |
| `main` | Release branch. Always a released state of `dev`. | Pull requests **from `dev` only**, with a **merge commit**. |
| `<type>/<issue>-<slug>` | One branch per issue, e.g. `feat/21-secret-scanning`, `docs/39-contribution-rules` | Created from the latest `origin/dev`. Deleted after merge. |

- **Every pull request targets `dev`.** The only exception is a release PR from `dev` into `main`.
- Never push directly to `dev` or `main`. Never force-push them.
- `<type>` is one of the commit types in §4.

```bash
git fetch origin
git switch -c feat/21-secret-scanning origin/dev
# ...work...
git push -u origin feat/21-secret-scanning
gh pr create --base dev --title "feat(ci): add secret scanning" --body-file pr-body.md  # body per §6
```

## 2. Working on an issue

Every change starts from a GitHub issue. Check its **Depends on** list and its *blocked by* links first. Don't start an issue while it is blocked; the [dependency map](https://github.com/affan80/REX/issues/111) shows the build order. Issues labelled `independent` can start any time.

1. **Plan before code.**
   - Re-read the issue and its acceptance criteria.
   - Check the **latest official documentation** for every tool, library or API the change touches: versions, flags, schemas, deprecations. Prefer official docs, release notes and changelogs over blog posts or memory.
   - Post the plan as a comment on the issue:
     - the files you'll touch;
     - the tests you'll add;
     - how each acceptance criterion will be met;
     - anything you will defer, with the reason.
2. **Wait for approval when the change is security-sensitive.** That covers authentication, authorization, crypto, sandboxing, network enforcement or exploit validation. The owner approves the plan before any code.
3. **Branch** from the latest `origin/dev` (§1).
4. **Test first** (§5).
5. **Open a pull request into `dev`** (§6).
6. **Close the issue** only when **every** acceptance criterion is met. Comment with a link to the PR and the evidence for each criterion. If part of the work moves to a later issue or phase, don't close it: comment what moved and why, and leave it open.

One issue, one branch, one pull request. If an issue turns out to be two concerns, split it into two issues.

## 3. Architecture decisions

Some choices are deliberately open: identity provider, broker, sandbox technology, policy engine and the others listed in `CLAUDE.md`. **Don't invent values for them.**
- Write an ADR in `docs/adr/` with the options and trade-offs (`status: proposed`).
- Link it to its `adr` issue.
- Let the owner decide in that ADR's pull request: the status becomes `accepted` or `rejected` before it merges.
- Code that depends on a decision is merged only after its ADR is `accepted`.
- Later changes get a new ADR; the old one becomes `deprecated` or `superseded by ADR-NNNN`. The full process is in [`docs/adr/README.md`](docs/adr/README.md).

## 4. Commits and pull-request titles

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). Pull-request titles follow the same format, and the squash commit on `dev` must use the PR title as its subject (set it when you merge until the repository default is changed in #32).

```
<type>(<optional scope>): <imperative summary, lower case, no period>

<body: what and why>

Refs #<issue>
```

`<type>` is one of `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `revert`. Dependency updates use `chore(deps): …`.

- Keep commits small and about one thing.
- Reference the issue in the body (`Refs #21`). Use `Closes #21` only in the PR that completes every acceptance criterion.
- Never commit secrets, credentials, `.env` files, samples or binaries (§7).

## 5. Tests

REX is test-driven.
1. Write the failing test.
2. Run it and watch it fail for the reason you expect.
3. Write the minimum code to pass.
4. Refactor.

- **Every security-sensitive change ships with a regression test** that fails without the change.
- Tests exercise real behaviour. Run the checker, script or code against controlled inputs and assert outcomes and exit codes. Don't search source text, and don't assert on mocks.
- Configuration files are validated by the tools that read them (schema validators, `uv lock --check`, linters), not by text-matching tests. Prose such as docs and ADRs needs no tests.
- Fixtures that look like secrets or binaries are **generated at test time** in a temporary directory. They are never committed.
- Before asking for review, run the full suite, not just your new test. Today that is:

  ```bash
  uv run --no-project --with pytest==9.2.0 --with markdown-it-py==4.3.0 pytest tests/repo
  uv run --no-project --with markdown-it-py==4.3.0 python scripts/check_docs.py
  ```

  These become `just test` and `just guards` once the dev tooling lands (#34). New files must be staged (`git add`) before `check_docs.py` sees them, because it checks what git tracks.

## 6. Pull requests

A pull request:
- targets **`dev`**;
- covers **one issue** and **one concern**;
- has a Conventional Commit title (§4);
- has a body with:
  - **Issue:** `Refs #N` (or `Closes #N` if it completes the issue);
  - **Plan:** a link to the plan comment on the issue;
  - **Acceptance criteria → evidence:** each criterion with the test, CI run or settings read-back that proves it;
  - **Tests run:** commands and results;
  - **Docs/ADRs updated:** yes or no, and which;
  - **Security-sensitive?** If yes, the link to the owner's approval;
  - **Risks and follow-ups.**

**Merging**
- All required checks are green. A pull request with a failing or skipped required check doesn't merge.
- A reviewer who didn't write the change has read the diff. For AI-written changes, that's a fresh review pass plus the owner's oversight.
- Merge into `dev` with **Squash and merge**. Delete the branch afterwards.
- Release: open a PR from `dev` into `main` and merge it with a **merge commit**. Only the owner merges releases.

Docs and ADRs are updated **in the same pull request** as the code they describe.

## 7. Samples, binaries and secrets

The repository is public. Anything committed can be copied before it is deleted.
- **Never commit samples or binaries.** That includes executables, archives, disk images, PCAPs from real targets, or anything that came from an untrusted source. Real samples live **outside the repository** in `~/.rex-samples/`, stored as password-protected archives (password `infected`, the industry convention).
- **Never run or unpack an unknown sample on your own machine.** Analysis runs only inside the REX sandboxes. Keep `~/.rex-samples/` out of cloud sync and backups.
- **No secrets anywhere:** not in code, tests, docs, issues, commit messages or logs. Local secrets go in `.env` / `.env.local`, which must never be committed (the repository `.gitignore` that ignores them lands with #37; until then, check `git status` before every commit). `.env.example` holds names only.
- **No Git LFS.** LFS objects are public too and hard to purge.
- If you commit a secret by mistake, **rotate it first**, then tell the owner privately (see §10). Removing it from history isn't enough.

## 8. Dependencies and licences

REX is Apache-2.0. Every new dependency needs a licence check before it is added.
- **Allowed:** MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, PSF-2.0, 0BSD, CC0-1.0, Unlicense, Zlib, MPL-2.0.
- **Not allowed** without a documented exception: GPL, AGPL, LGPL (as linked dependencies), SSPL, BUSL, or no/unknown licence.

Pin versions through the lockfiles (`uv.lock`, `pnpm-lock.yaml`) and commit them. Prefer the latest stable release, checked against its official release notes.

## 9. AI agents in this repository

AI coding agents follow the same rules as people, plus these:
- `CLAUDE.md` holds the project rules. Repository settings in `.claude/` (permissions, sandbox, hooks; added with #35) enforce the safety-critical ones. Agents must not weaken them; only humans edit `.claude/`.
- Agents post their plan on the issue before coding, and report at the end what changed, which tests ran with their results, and any open risks.
- Optional personal plugins (for example *superpowers* or *ponytail*) are each contributor's choice and are not configured in the repository. Install ponytail only from `DietrichGebert/ponytail`, and **leave its webhook URL empty** so task data never leaves your machine. `CLAUDE.md` and these rules override any plugin's defaults.

## 10. Reporting security problems

Don't open a public issue for a vulnerability. Use GitHub's **private vulnerability reporting** (Security tab → *Report a vulnerability*); it is enabled for this repository. A `SECURITY.md` with the full policy lands with #32.
