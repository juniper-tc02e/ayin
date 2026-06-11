# Ayin backend (Python)

FastAPI API gateway + Celery workers — the scanning core: connectors, entity resolution, scoring, safety, and the PII vault.

## Planned layout (created as you work through `../docs/BUILD-PLAN.md`)

```
ayin/
  api/           FastAPI app — routes, deps, schemas (auth, scans, findings, …)
  analytics/     privacy-screened funnel events + §13.7 report CLI
  auth/          passwords (argon2), JWTs (session/step-up), verification tokens
  beta/          invite tooling + the go/no-go scorecard CLI (M5)
  connectors/    uniform connector contract + breach / search / broker registry
  models/        data model (Alembic migrations live in ../migrations)
  orchestrator/  scan job state machine (queued→gated→running→…→done|held)
  qa/            findings-accuracy QA harness (sample → review → report)
  remediation/   read-only hardening checklist with honest score deltas
  resolution/    entity resolution — dedupe, anti-namesake matching, review
  safety/        audit log, gates (ToS/abuse/limits), exclusion, visibility
  scoring/       versioned Exposure Score rubric + engine
  services/      email/SMS senders, identifier normalization
  vault/         PII vault (envelope encryption, retention, crypto-shred)
tests/           174+ tests (pgserver-backed — no Docker needed)
```

## Run

```bash
pip install -e ".[dev]"                          # once
python -m alembic upgrade head                   # apply migrations
uvicorn ayin.api.main:app --reload               # API → :8000
celery -A ayin.orchestrator worker -l info       # workers (from M1-1)
python -m pytest                                 # tests — no Docker needed (pgserver + fakeredis)
python -m ruff check . && python -m mypy ayin    # lint + types
```

Config comes from env / `../.env` (see `../.env.example`). Tests boot their own
throwaway Postgres and apply migrations from scratch each session.

## Rules (see `../CLAUDE.md`)

- **Connector contract first** — never call a source API from business logic.
- **Every finding** carries `source` + `captured_at` + `confidence`.
- **Any subject-data access writes an `AuditRecord`** — including internal access.
- Never persist or render full plaintext stolen credentials (exposure status / partial only).
