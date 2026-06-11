# Ayin — task runner (M0-1). On Windows run via Git Bash or WSL,
# or use the raw commands documented in README.md.

.PHONY: dev down api web worker test lint fmt migrate revision funnel gonogo qa-sample invites

dev:            ## boot the full local stack (Postgres+Redis+MinIO+MailDev+api+web)
	docker compose up

down:           ## stop the stack
	docker compose down

api:            ## run the API locally (needs Postgres/Redis from `docker compose up postgres redis`)
	cd backend && uvicorn ayin.api.main:app --reload --port 8000

web:            ## run the frontend locally
	cd frontend && npm run dev

worker:         ## run a Celery worker (+beat)
	cd backend && celery -A ayin.orchestrator.celery_app:celery_app worker -B -l info

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

funnel:         ## print the §13.7 funnel (make funnel days=7)
	cd backend && python -m ayin.analytics.report $(if $(days),--days $(days),)

gonogo:         ## the §13.7 go/no-go scorecard (make gonogo qa=path.jsonl)
	cd backend && python -m ayin.beta.gonogo $(if $(qa),--qa-reviewed $(qa),)

qa-sample:      ## export a findings-accuracy review sample (make qa-sample n=50 out=sample.jsonl)
	cd backend && python -m ayin.qa.sample --n $(or $(n),50) --out $(or $(out),qa-sample.jsonl)

invites:        ## create beta invites (make invites count=10 note=wave-1)
	cd backend && python -m ayin.beta.invites create --count $(or $(count),1) $(if $(note),--note $(note),)
