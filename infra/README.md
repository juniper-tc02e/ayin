# Ayin infrastructure

Terraform / IaC for cloud deploys — added in **Phase 1** (PRD §10.5). Local development uses Docker Compose at the repo root (BUILD-PLAN M0-1), not this directory.

When built, targets include: containers (ECS or K8s), Postgres, Redis, object storage, a **KMS for the PII vault** (per-subject field keys → crypto-shred), and **per-connector cost dashboards** — data-API spend is the dominant variable cost and COGS visibility is existential (PRD §10.8, §17.2). Secrets come from a managed vault, never from committed config.
