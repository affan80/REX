---
status: accepted
date: 2026-11-27
decision-makers: affan80
issue: "#39"
---

# Record architecture decisions as MADR files in docs/adr

## Context and Problem Statement

REX has many decisions that are deliberately still open (identity provider, broker, sandbox technology, policy engine and others, tracked as `adr` issues #1–#17). The project rules forbid inventing values for them: each needs options, trade-offs and an owner decision that later contributors and AI agents can find and trust. How do we record those decisions?

## Decision Drivers

* Decisions must be reviewable in pull requests, next to the code they shape.
* Contributors and AI agents must be able to find the current decision and its status without asking.
* Licence and security impact (hard rules 1–14) must be stated for every option.
* Low ceremony for a sole maintainer.

## Considered Options

* Markdown ADRs in the repository, using MADR 4.0.0 with a REX template
* Free-form design notes in issues or a wiki
* No formal record; decisions live in commit messages and chat

## Decision Outcome

Chosen option: "Markdown ADRs in the repository, using MADR 4.0.0 with a REX template", because it keeps decisions versioned and reviewed with the code, gives every decision a status and date that tools can check, and MADR is the most widely used, maintained ADR format (4.0.0 is the current release).

### Consequences

* Good, because each decision has an owner-approved status, a date and its options, findable at `docs/adr/`.
* Good, because the ADR changes in the same pull request as the code that depends on it.
* Bad, because ADRs can drift from the index or link to removed files; this is handled by the checker below.

### Confirmation

* `scripts/check_docs.py` (tested by `tests/repo/test_check_docs.py`) enforces file naming (`NNNN-kebab-title.md`), unique contiguous numbers, a valid MADR status and date in the front matter, an index entry in `docs/adr/README.md` for every ADR, and working relative links. It runs locally now and in CI once the CI baseline (#18) lands.
* Process rules are in `CONTRIBUTING.md` §3.

## Pros and Cons of the Options

### Markdown ADRs in the repository (MADR 4.0.0)

* Good, because versioned and reviewed with code; works offline and in any editor.
* Good, because the format is a published, maintained standard with tooling and examples.
* Neutral, because it needs a small checker to keep the index honest.
* Licence: MADR is `MIT OR CC0-1.0` — both on the REX allowlist.
* Security: no impact on runtime; decisions themselves must state their security impact.

### Free-form notes in issues or a wiki

* Good, because quick to write.
* Bad, because not versioned with the code, easy to lose, no status a tool can check, and the GitHub wiki is not reviewed through pull requests.

### No formal record

* Good, because zero effort.
* Bad, because it breaks the project rule that open decisions are decided explicitly by the owner, and agents would fill gaps by guessing.

## More Information

* MADR 4.0.0: https://adr.github.io/madr/ (checked 2026-11-27; latest release 4.0.0).
* Template: [0000-template.md](0000-template.md). Index and process: [README.md](README.md).
* Revisit if the number of ADRs makes a generated index or a docs site worthwhile.
