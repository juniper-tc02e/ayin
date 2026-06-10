# Ayin — Claude Code project guide

Ayin is an open-source-intelligence (OSINT) **self-exposure scanner**: it shows a person what the internet already knows about them (breaches, data-broker listings, public/social footprint), scores the exposure 0–100, and helps them shrink it. The wedge is a free **self-scan**; the business is monitoring + removal.

**The full spec is [`docs/Ayin-PRD-and-SaaS-Plan.md`](docs/Ayin-PRD-and-SaaS-Plan.md). Read it before non-trivial work.** This file is the operating contract; the PRD is the source of truth. The current build sequence is [`docs/BUILD-PLAN.md`](docs/BUILD-PLAN.md).

---

## Non-negotiable constraints (load-bearing — never relax)

These are the difference between a privacy product and a liability. If a task seems to require breaking one, stop and flag it instead of proceeding.

1. **MVP is self-scan only (Tier T0).** A requester may only scan identifiers they have *verified they control*. No third-party scanning ships in the MVP — don't build endpoints, jobs, or UI that scan a subject who isn't the verified requester.
2. **The FCRA bright line.** Ayin is NOT a consumer reporting agency. Never produce eligibility/character/credit/employability scoring, and never build anything usable for hiring, tenant, credit, or insurance decisions. The Exposure Score measures *exposure and exploitability of data*, never the person.
3. **"Publicly available" is strict.** In scope: data accessible to anyone without authenticating, without defeating a technical control, and without violating the source's terms. Out of scope (never implement): auth bypass, credential stuffing, scraping behind logins or against ToS, buying breached/stolen data or dark-web dumps, contacts-only content, and any data about minors. Each connector declares its legal basis + access method.
4. **Safety floor ships in every build — never a paid upsell.** Audit log, rate/volume limits, abuse refusal, "Exclude me from Ayin," delete-everything, and short retention are present from the first scan.
5. **Sources, not assertions.** Every finding carries source + captured-at + confidence. No mystery data. LLMs may *summarize* retrieved, sourced findings; they may never invent findings or speculate about a person (hallucination here is a defamation/safety risk, not a UX bug).
6. **Minimize what we keep.** Store findings + score, not permanent raw dossiers. Encryption everywhere; retention timers; crypto-shred on delete. Never build a sellable index. Never sell subject data.
7. **Audit from the first scan.** Every scan and every access to subject data — including internal/staff access — writes an immutable audit record. Staff are not exempt from the trust model.

**Decision rule for any new feature (PRD §20.5):** *is this more valuable to someone protecting themselves than to someone targeting another person, and can we verify the requester, bound the purpose, rate-limit, audit, and let subjects exclude themselves?* If not, it doesn't ship.

---

## Architecture (PRD §10)

The scan is an **8-step pipeline** run as an asynchronous, resumable job — not a synchronous request:

```
INPUT → DISCOVERY → RESOLUTION → ENRICHMENT → SCORING → REPORT → REMEDIATION → MONITORING
```

MVP implements steps 1–6 for self-scan. Architectural rules:

- **Connectors are isolated and swappable** behind one uniform contract (auth, rate-limit, normalize, error/backoff, ToS + legal metadata, cost telemetry). Add/version/kill a source without touching the core. Business logic never calls a source API directly.
- **Safety checks are pipeline gates**, not async side-effects — a gate can refuse a job before it runs.
- **PII is a vault, not a table** — sensitive subject data lives in an encrypted, access-controlled, short-retention store, separate from operational data.

### Tech stack (recommended default — PRD §10.5; change deliberately and record in `docs/adr/`)

- **Frontend:** Next.js + TypeScript (App Router) — B2C self-scan UI.
- **Backend:** Python — FastAPI (API gateway: authn/z, tiering, rate-limit) + Celery workers (connectors, entity resolution, scoring). Python is chosen for the scraping/parsing/ER/ML core.
- **Datastores:** Postgres (operational + findings; Postgres FTS for MVP, defer OpenSearch), Redis (cache, rate-limit, Celery broker), object storage (S3 / MinIO locally) for raw artifacts.
- **PII vault:** dedicated encrypted store with per-subject field-level keys (KMS in cloud; libsodium/age locally) enabling crypto-shred.
- **Orchestration:** Celery + Postgres-backed job state for MVP. Temporal is the Phase-1 upgrade when resumability/retries demand it — keep the orchestrator behind an interface so the swap is cheap.
- **Local dev:** Docker Compose (Postgres + Redis + MinIO). Terraform/IaC lives in `infra/`, added in Phase 1.

### Repo layout (target)

```
Ayin/
├── CLAUDE.md                       # this file
├── README.md
├── docs/
│   ├── Ayin-PRD-and-SaaS-Plan.md   # source of truth
│   ├── BUILD-PLAN.md               # phased, Claude-Code-sized tasks
│   └── adr/                        # architecture decision records
├── frontend/                       # Next.js self-scan UI
├── backend/
│   └── ayin/
│       ├── api/          # FastAPI: auth, tiering, rate-limit, routes
│       ├── orchestrator/ # scan job state machine (queued→gated→running→…→done/held)
│       ├── connectors/   # base contract + breach / search / broker (MVP)
│       ├── resolution/   # entity resolution (rules + thresholds for MVP)
│       ├── scoring/      # versioned Exposure Score
│       ├── safety/       # T&S gates, abuse heuristics, audit log, exclude-me
│       ├── vault/        # PII vault (encrypt, retention, crypto-shred)
│       └── models/       # data model (see below)
└── infra/                          # Terraform / IaC (Phase 1)
```

### Core data model (PRD §10.4)

`User/Org` · `Subject` · `Identifier` · `Scan` · `Finding` · `Score` · `RemediationTask` · `AuditRecord` · `AbuseSignal/ReviewCase`. The `AuditRecord` is the spine — write it on every scan and every subject-data access.

---

## How to work in this repo

- **Read `docs/BUILD-PLAN.md`, find the current phase, build in that order.** Don't pull Phase 2+ work forward.
- **Connector contract first.** Every data source implements the same interface; never reach into a source's API from business logic.
- **Every finding gets source + confidence + captured-at** — including in tests and fixtures.
- **Touching subject data? Write an audit record.** If there's no clean way to, that's a bug to surface, not skip.
- **Tests:** cover the connector contract, entity-resolution thresholds (false-merge is the enemy — PRD FR-ER-1), and the scoring rubric. Maintain a findings-accuracy QA harness (target ≥ 90% precision on shown findings — PRD §13.7).
- **Keep changes surgical.** Smallest change that satisfies the FR; surface assumptions; don't refactor unrelated code.
- Conventional Commits; scope each PR to one FR / build-plan item where possible.

## Security & data handling (hard rules)

- **Never commit** real scan data, PII, breach/credential samples, `.env` files, or secrets. Fixtures use clearly fake data only.
- Treat all third-party data as untrusted input — validate and normalize at the connector boundary.
- **Never display full plaintext stolen credentials** — show exposure *status* / partial only (PRD FR-DISC-1).
- Don't add a data source without its governance record: legal basis, access method, ToS ref, data classes, cost/call, rate limits, counsel sign-off flag (PRD §11.4).
- `.claude/settings.json` denies the agent read access to `.env*` and vault/secret paths — don't work around it.

## Definition of done (MVP feature)

Meets its FR acceptance criteria (PRD §9) · safety floor intact · findings sourced + confidence-tagged · audit record written for any subject-data access · tests pass · no PII/secrets committed · assumptions noted in the PR.
