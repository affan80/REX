---
# Copy this file to docs/adr/NNNN-kebab-case-title.md (next free number) and fill it in.
# status: proposed | rejected | accepted | deprecated | superseded by ADR-NNNN
status: proposed
# date: YYYY-MM-DD when the decision was last updated
date: 2026-01-01
decision-makers: affan80
issue: "#N"
---

<!-- REX ADR template, based on MADR 4.0.0 (https://adr.github.io/madr/), licensed MIT OR CC0-1.0. -->

# {Short title of the solved problem and the chosen solution}

## Context and Problem Statement

{Two or three sentences: what problem, why now, what is in scope. Link the `adr` issue. Open REX decisions are never decided by inventing values; list the facts and constraints instead.}

## Decision Drivers

* {Hard rule(s) from CLAUDE.md this decision must respect, e.g. "Rule 3: deny by default"}
* {Quality or constraint, e.g. "runs on the 3-PC lab", "sole maintainer can operate it"}

## Considered Options

* {Option 1}
* {Option 2}
* {Option 3}

## Decision Outcome

Chosen option: "{Option N}", because {justification tied to the decision drivers}.

### Consequences

* Good, because {…}
* Bad, because {…}

### Confirmation

{How compliance is checked: the test, CI check, policy or review that proves the implementation follows this decision.}

## Pros and Cons of the Options

### {Option 1}

* Good, because {…}
* Neutral, because {…}
* Bad, because {…}
* Licence: {SPDX id} — {on the allowlist in CONTRIBUTING.md §8? the full policy lands in docs/security/dependency-licenses.md with #38}
* Security: {impact on the hard rules: isolation, secrets, cross-project data, evidence}

### {Option 2}

* Good, because {…}
* Bad, because {…}
* Licence: {SPDX id}
* Security: {…}

## More Information

{Sources checked (latest official docs, with dates), follow-up issues, and when to revisit this decision.}
