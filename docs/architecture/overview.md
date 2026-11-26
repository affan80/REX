# REX architecture overview

REX is an AI-assisted reverse-engineering and security-research platform. Users upload **untrusted** artifacts (binaries, APK/IPA, firmware, PCAPs, source code). REX stores and identifies them safely, runs analysis tools in isolated sandboxes, records **signed evidence**, uses a multi-model AI *Council* to help interpret results, and produces findings and reports.

> **AI is a helper, never proof. Evidence is proof.** A finding must link to evidence; AI claims or Council agreement alone are never enough.

This page shows the target architecture as [C4](https://c4model.com/) diagrams (level 1: context, level 2: containers). Diagrams use Mermaid `flowchart` with C4 notation because Mermaid's dedicated C4 diagram type is still experimental. Boxes marked **ADR #N** are deliberately open decisions: they are drawn by role only, and the technology is chosen in that ADR, never assumed here.

## Level 1 — System context

```mermaid
flowchart TB
    researcher["👤 <b>Security researcher</b><br/>[Person]<br/>Uploads artifacts, reviews evidence,<br/>findings and reports"]
    owner["👤 <b>Platform owner</b><br/>[Person]<br/>Approves scopes, policies,<br/>exploit-validation permits"]

    rex["<b>REX</b><br/>[Software system]<br/>Stores and identifies artifacts, runs isolated analysis,<br/>records signed evidence, produces findings and reports"]

    idp["<b>Identity provider</b><br/>[External system, OIDC]<br/>ADR #3"]
    ai["<b>AI model providers</b><br/>[External systems]<br/>Official APIs only"]
    feeds["<b>Vulnerability and rule feeds</b><br/>[External systems]<br/>e.g. vulnerability databases"]
    targets["<b>Authorized external targets</b><br/>[External systems]<br/>Only with verified authorization, ADR #13"]

    researcher -- "Uses (web, CLI, SDK)" --> rex
    owner -- "Administers, approves" --> rex
    rex -- "Authenticates users via OIDC" --> idp
    rex -- "Sends redacted, classified context (ADR #12)" --> ai
    rex -- "Fetches updates through the PC 3 gateway" --> feeds
    rex -. "Validation traffic only, approved scope, via PC 3" .-> targets

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef system fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#6b6b6b,stroke:#4d4d4d,color:#fff
    class researcher,owner person
    class rex system
    class idp,ai,feeds,targets external
```

## Level 2 — Containers on the 3-PC lab

The lab is three machines with separate trust levels. Untrusted content is never parsed or executed in the control plane. Workers hold no control-plane credentials and no signing keys: they get per-job, short-lived, pre-signed access to one artifact and return raw results; a trusted evidence service on PC 1 hashes, signs and records them. All worker network traffic goes through PC 3, which never trusts worker-supplied values.

```mermaid
flowchart LR
    user["👤 Researcher / owner"]

    subgraph PC1["PC 1 — Control plane (trusted)"]
        web["<b>Web app</b><br/>[Next.js + TypeScript]<br/>apps/web"]
        api["<b>API</b><br/>[Python, FastAPI]<br/>services/api<br/>AuthN/AuthZ, deny by default.<br/>Never parses artifacts"]
        sched["<b>Scheduler</b><br/>[Python]<br/>services/scheduler<br/>Pipelines, execution permits"]
        aigw["<b>AI gateway</b><br/>[Python]<br/>services/ai-gateway<br/>Redaction, budgets, Council"]
        integ["<b>Integration service</b><br/>[Python]<br/>services/integration-service"]
        db[("<b>Database</b><br/>[PostgreSQL + pgvector]<br/>Projects, evidence index,<br/>findings, search")]
        obj[("<b>Object storage</b><br/>[S3-compatible, ADR #4]<br/>Quarantined artifacts,<br/>derived outputs")]
        queue[("<b>Queue / broker</b><br/>[ADR #5]")]
        policy["<b>Policy engine</b><br/>[ADR #7]"]
        evidence["<b>Evidence service</b><br/>[Python, #57]<br/>Hashes, signs (vetted crypto)<br/>and records results.<br/>Signing keys never leave PC 1"]
    end

    subgraph PC2["PC 2 — Workers (untrusted execution)"]
        sandbox["<b>Sandbox</b><br/>[ADR #6: gVisor / Firecracker / VM]"]
        wa["<b>Analysis workers</b><br/>workers/analysis<br/>YARA, Syft, Grype, Semgrep,<br/>Trivy, Binwalk, TShark, Zeek"]
        wre["<b>Reverse-engineering workers</b><br/>workers/reverse-engineering<br/>radare2, Ghidra, JADX, Apktool"]
        wdyn["<b>Dynamic workers</b><br/>workers/dynamic<br/>Frida, GDB, LLDB"]
        wval["<b>Validation workers</b><br/>workers/validation<br/>Offline first, permit + scope"]
    end

    subgraph PC3["PC 3 — Security gateway"]
        gw["<b>Network gateway</b><br/>infrastructure/pc3-security-gateway<br/>Destinations, protocols, budgets.<br/>Never trusts worker values. VPN role: ADR #9"]
    end

    ext["External feeds, AI providers,<br/>authorized targets"]

    user -- "HTTPS (OIDC)" --> web
    web -- "HTTPS, versioned API" --> api
    api --> db
    api -- "Streams uploads (≤ 2 GB)" --> obj
    api --> policy
    api --> queue
    sched --> queue
    sched -- "Signs execution permits (ADR #8)" --> queue
    aigw -- "Official provider APIs only" --> gw
    integ -- "Outbound only" --> gw

    queue -- "Jobs + permits (mTLS)" --> sandbox
    sandbox --- wa
    sandbox --- wre
    sandbox --- wdyn
    sandbox --- wval
    obj -- "One artifact per job<br/>(pre-signed, short-lived URL)" --> sandbox
    sandbox -- "Raw results (untrusted)" --> evidence
    evidence -- "Signed evidence records" --> db
    evidence -- "Derived outputs" --> obj
    sandbox -- "All egress" --> gw
    gw -- "Allowlisted destinations only" --> ext

    classDef trusted fill:#1168bd,stroke:#0b4884,color:#fff
    classDef store fill:#2f6f9f,stroke:#1d4a6b,color:#fff
    classDef untrusted fill:#a33b2b,stroke:#6e271d,color:#fff
    classDef gateway fill:#8a6d1d,stroke:#5c4913,color:#fff
    classDef open fill:#6b6b6b,stroke:#4d4d4d,color:#fff,stroke-dasharray: 4 3
    class web,api,sched,aigw,integ,evidence trusted
    class db store
    class wa,wre,wdyn,wval untrusted
    class gw gateway
    class obj,queue,policy,sandbox open
```

## Trust boundaries and the rules they enforce

Rule numbers refer to the hard rules in `CLAUDE.md` (added with #35).

| Boundary | What crosses it | Rules that apply (CLAUDE.md) |
|---|---|---|
| User ↔ API | Uploads, requests | 3 deny-by-default authorization per project + operation; 4 max 2 GB, content-based identification |
| API ↔ object storage | Raw artifacts | 2 API never parses or executes untrusted content; 10 per-project isolation |
| Control plane (PC 1) ↔ workers (PC 2) | Jobs, execution permits, raw results | 1 tool output is untrusted; 5 extraction limits; workers hold no control-plane credentials or signing keys |
| Workers (PC 2) ↔ gateway (PC 3) ↔ internet | All network traffic | 6 no external targets without verified authorization; 7 gateway enforces destinations, protocols, budgets |
| Platform ↔ AI providers | Classified, redacted context | 8 AI is never proof; 9 no secrets in prompts; 12 official provider APIs only |
| Evidence service (PC 1) | Raw results in, signed records out | 8 findings link to evidence; 11 vetted crypto only; signing happens only in the trusted zone |

The detailed threat model is tracked in #40.

## Where things live

| Area | Path |
|---|---|
| Web app | `apps/web` |
| Control-plane services | `services/{api,scheduler,ai-gateway,integration-service}` |
| Workers | `workers/{analysis,dynamic,reverse-engineering,validation}` |
| Shared contracts and SDKs | `packages/{contracts,python-sdk,typescript-sdk,cli,plugin-sdk,tool-adapters,shared-config}` |
| Infrastructure | `infrastructure/{compose,k3s,pc1-control-plane,pc2-workers,pc3-security-gateway,monitoring,backup-recovery}` |
| Decisions | [`docs/adr/`](../adr/README.md) |

Service boundaries: no service imports another service's private code; shared types live only in `packages/contracts`.

## Open decisions shown on these diagrams

| Element | Decision issue |
|---|---|
| Identity provider | #3 |
| Object storage product | #4 |
| Message broker | #5 |
| Sandbox technology | #6 |
| Policy engine | #7 |
| Execution-permit signing and revocation | #8 |
| PC 3 VPN role | #9 |
| AI data classification and redaction | #12 |
| External-target authorization proof | #13 |
