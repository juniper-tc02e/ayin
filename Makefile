# Ayin — task runner (M0-1). On Windows run via Git Bash or WSL,
# or use the raw commands documented in README.md.

.PHONY: dev down api web worker test lint fmt migrate revision

dev:            ## boot the full local stack (Postgres+Redis+MinIO+MailDev+api+web)
	docker compose up

down:           ## stop the stack
	docker compose down

api:            ## run the API locally (needs Postgres/Redis from `docker compose up postgres redis`)
	cd backend && uvicorn ayin.api.main:app --reload --port 8000

web:            ## run the frontend locally
	cd frontend && npm run dev

worker:         ## run a Celery worker (from M1-1 on)
	cd backend && celery -A ayin.orchestrator worker -l info

test:           ## backend tests (self-contained: pgserver + fakeredis, no Docker needed)
	cd backend && python -m pytest -q

lint:           ## ruff + mypy
	cd backend && python -m ruff check . && python -m mypy ayin

fmt:            ## auto-format
	cd backend && python -m ruff check --fix . && python -m ruff format .

migrate:        ## apply DB migrations
	cd backend && python -m alembic upgrade head

revision:       ## new migration: make revision m="message"
	cd backend && python -m alembic revision --autogenerate -m "$(m)"
