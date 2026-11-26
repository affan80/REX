# Architecture decision records

REX records every significant or deliberately open decision as an ADR in this folder, using [MADR 4.0.0](https://adr.github.io/madr/). Why we do this: [ADR-0001](0001-record-architecture-decisions.md).

## Process

1. **Find or open the `adr` issue.** Open decisions are tracked as issues labelled `adr` and `needs-decision` (#1–#17). Never invent a value for one of them.
2. **Copy the template.** Copy [`0000-template.md`](0000-template.md) to `NNNN-kebab-case-title.md` with the next free number, and set `status: proposed`.
3. **Check the latest official docs** for every option (versions, licences, security notes) and record the sources and dates under *More Information*.
4. **Open a pull request into `dev`.** It contains the ADR and its line in the index below. The owner decides and the status becomes `accepted` or `rejected`.
5. **Change later decisions with a new ADR.** Write a new ADR with `status: proposed`, and once it is accepted set the old one to `superseded by ADR-NNNN`. Never rewrite an accepted ADR's decision.

`scripts/check_docs.py` checks naming, numbering, status, date, this index, and links. Run it with:

```bash
uv run --no-project --with markdown-it-py==4.3.0 python scripts/check_docs.py
```

## Index

| ADR | Title | Status | Issue |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions as MADR files in docs/adr | accepted | #39 |
| [0002](0002-monorepo-workspace-tooling.md) | Use uv workspaces, pnpm workspaces and a justfile for the REX monorepo | accepted | #1 |
