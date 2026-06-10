# Ayin

> *ʿayin* (Hebrew, "eye" / "to see") — an open-source-intelligence scanner that shows a person exactly what the internet already knows about them, scores the risk, and helps them shrink it.

Ayin performs an OSINT scan of a person from **publicly available** sources — breached credentials, data-broker listings, public/social footprint — resolves it into one profile, scores the exposure 0–100, and drives remediation. The model is **open OSINT with hard safeguards**: the defensive, consent-forward "show me what's exposed about *me*, then help me remove it" use case is the wedge.

**The MVP is self-scan only.** A user can only scan identifiers they have verified they control. No third-party scanning ships until the trust core is proven.

## Documentation

- **[`docs/Ayin-PRD-and-SaaS-Plan.md`](docs/Ayin-PRD-and-SaaS-Plan.md)** — the full product/architecture/business spec (source of truth).
- **[`docs/BUILD-PLAN.md`](docs/BUILD-PLAN.md)** — the MVP, sequenced into build tickets.
- **[`CLAUDE.md`](CLAUDE.md)** — operating constraints + conventions (read first if you're building).

## Architecture (short version)

The scan is an 8-step async pipeline — `INPUT → DISCOVERY → RESOLUTION → ENRICHMENT → SCORING → REPORT → REMEDIATION → MONITORING` — with swappable source connectors, safety checks as pipeline gates, an encrypted PII vault, and an immutable audit log. Full detail in PRD §10.

**Stack (recommended default):** Next.js + TypeScript frontend · Python (FastAPI + Celery) backend · Postgres + Redis + object storage · Docker Compose for local dev. See `CLAUDE.md` for rationale; deviations get an ADR in `docs/adr/`.

## Quickstart (local dev)

> Prerequisites: Docker Desktop, Node 20+, Python 3.10+, Git.

```bash
# 1. configure environment
cp .env.example .env        # then fill in the placeholders

# 2. boot the local stack (Postgres + Redis + MinIO + api + web)
docker compose up

# api → http://localhost:8000   web → http://localhost:3000
# maildev (dev email inbox) → http://localhost:1080

# 3. apply database migrations (first run, and after pulling new ones)
cd backend && pip install -e ".[dev]" && python -m alembic upgrade head
```

Backend tests run **without Docker** (throwaway Postgres via `pgserver`):

```bash
cd backend && python -m pytest
```

## Working on Ayin with Claude Code

```bash
claude            # from this folder; it reads CLAUDE.md automatically
```

Then, e.g.: *"Read CLAUDE.md and docs/BUILD-PLAN.md, then implement ticket M0-1."* Build milestones in order; don't pull later-phase work forward.

## Non-negotiables (the load-bearing rules)

- Self-scan only (T0) in the MVP — verified-control identifiers only.
- Not a consumer reporting agency — no eligibility/character scoring, ever (the FCRA line).
- Strict "publicly available" definition — no auth bypass, no scraping behind logins, no buying stolen data, no minors.
- Safety floor (audit, rate limits, abuse refusal, exclude-me, delete-everything, short retention) in **every** build.
- Every finding is sourced + confidence-tagged. Never commit real PII, scan data, or secrets.

See `CLAUDE.md` and PRD §7, §19, §20 for the full trust architecture.

## Status

Pre-MVP — **milestones M0 (Foundations) and M1 (Discovery) complete**: resumable scan orchestrator with safety gates in the critical path, three real connectors behind the uniform contract (breach/HIBP-class, public-web search, data-broker detection with a 25-broker opt-out registry), encrypted PII vault with crypto-shred, live-tunable rate limits, and the scan UI (launch → progress → findings with step-up unlock). Real connectors are env-key-gated (`BREACH_API_KEY`, `SEARCH_API_KEY`) and production-locked behind governance counsel sign-off; dev runs ship a clearly-labeled FakeConnector so the loop works with zero keys. Next: M2 (Resolution + scoring). Building toward the §13.7 go/no-go.

---

*This is a privacy and safety product before it is a scanner. When in doubt, choose the option that protects the subject.*
