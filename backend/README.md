# Ayin backend (Python)

FastAPI API gateway + Celery workers — the scanning core: connectors, entity resolution, scoring, safety, and the PII vault.

## Planned layout (created as you work through `../docs/BUILD-PLAN.md`)

```
ayin/
  api/           FastAPI app — auth, tiering, rate-limit, routes
  orchestrator/  scan job state machine (Celery tasks; queued→gated→running→…→done|held)
  connectors/    uniform connector contract + breach / search / broker (MVP)
  resolution/    entity resolution (rules + thresholds for MVP)
  scoring/       versioned Exposure Score
  safety/        T&S gates, abuse heuristics, audit log, exclude-me
  vault/         PII vault (encrypt, retention, crypto-shred)
  models/        data model + Alembic migrations
tests/           unit tests + findings-accuracy QA harness
```

## Run (once scaffolded — BUILD-PLAN M0-1)

```bash
uvicorn ayin.api.main:app --reload              # API → :8000
celery -A ayin.orchestrator worker -l info      # workers
pytest                                          # tests
```

## Rules (see `../CLAUDE.md`)

- **Connector contract first** — never call a source API from business logic.
- **Every finding** carries `source` + `captured_at` + `confidence`.
- **Any subject-data access writes an `AuditRecord`** — including internal access.
- Never persist or render full plaintext stolen credentials (exposure status / partial only).
