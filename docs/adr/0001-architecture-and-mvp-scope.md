# ADR 0001 — Architecture & MVP scope

- **Status:** Accepted (records decisions from PRD §22.1)
- **Date:** 2026-06-10
- **Context:** Porting the Ayin PRD into a buildable repo. We need the load-bearing technical and scope decisions written down before code so Claude Code (and any contributor) builds consistently.

## Decision

**Scan model.** Open OSINT with hard safeguards. **The MVP is self-scan only (Tier T0)** — a requester may scan only identifiers they have verified they control. No third-party scanning (T1–T3) in the MVP; this removes the entire high-risk surface while we prove value.

**Architecture.** Scan-as-pipeline (8 steps, async, resumable). Source **connectors are isolated behind one uniform contract** so sources are swappable without touching the core. **Safety checks are pipeline gates** that can refuse a job. **PII lives in an encrypted vault** (per-subject keys, short retention, crypto-shred), separate from operational data. **Immutable audit log from the first scan**, covering internal access too.

**Stack (default; deviations get a new ADR).** Next.js + TypeScript frontend; Python backend (FastAPI gateway + Celery workers) for the scraping/parsing/ER/ML core; Postgres (operational + findings, FTS for MVP) + Redis (cache, rate-limit, broker) + object storage (artifacts); Docker Compose for local dev. Orchestration is Celery + Postgres-backed job state for the MVP, with Temporal as the Phase-1 upgrade behind an orchestrator interface.

**MVP source coverage.** Three connectors only — one breach/credential provider (HIBP-class), one compliant search/public-web method, and a hand-curated ~20–50 high-impact US data-broker detection set. Depth across categories over breadth of brokers.

## Consequences

- T0-only keeps the first build legally simple and lets us ship the safety floor without compromise. Everything cut from the MVP (automation, monitoring, third-party tiers, B2B) is expansion of the *same* loop — nothing here will be thrown away.
- The connector contract and audit log cost a little upfront and are foundational forever; retrofitting them later would be painful.
- Python-first backend optimizes for the data/ER work at the cost of a second language alongside the TS frontend; shared types come from the API's OpenAPI schema.
- Locking T0-only means reviewers must reject any PR that introduces non-self scanning until a future ADR opens a higher tier with its full safeguard set.

## Open questions (PRD §22.3 — decide before they block work)

Primary launch geography (US-first recommended) · breach data provider + backup and credential-display rules · broker coverage depth at GA · score-rubric governance · entity-resolution build-vs-buy threshold. Record each as its own ADR when decided.
