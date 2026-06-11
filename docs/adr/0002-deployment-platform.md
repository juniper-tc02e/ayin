# ADR 0002 — Beta deployment platform: managed PaaS (Render), AWS deferred

- **Status:** Accepted
- **Date:** 2026-06-11
- **Context:** MVP is code-complete; the private beta (25–50 users, §13.7
  measurement) needs hosting. PRD §10.5 names AWS/GCP + Terraform as the GA
  posture. The operator is a solo founder whose scarce resource during the
  beta is attention — every ops hour competes with user research hours.

## Decision

**Render** hosts the beta: Docker services for api / worker / web, managed
Postgres 16 (PITR, 7-day backup retention per LAUNCH-PLAN D-8) and managed
Redis, staging + production from `render.yaml`. Region: US (US-first
launch, PRD §22.3). Fly.io is the evaluated runner-up (comparable model;
Render's managed-Postgres + preDeploy-migration ergonomics won). A single
VPS was rejected — it converts founder attention into patching/backup/TLS
labor during the exact weeks that belong to users. AWS-from-day-one was
rejected for the same reason at ~3× the setup cost, with one real loss,
acknowledged below.

## Consequences

- **Accepted tradeoff — no KMS:** `VAULT_MASTER_KEY` lives as a Render env
  var, not in a hardware-backed KMS. Mitigations: founder-only env access
  with 2FA, the no-PII logging policy (the key can never reach logs),
  a tested rotation/re-wrap runbook (LAUNCH-PLAN D-4), short backup
  retention. **AWS + KMS migration is a committed Phase-1 item on the GO
  path** (LAUNCH-PLAN T-9) — this ADR expires with that migration.
- Terraform stays deferred; `render.yaml` is the IaC for now and the
  Phase-1 migration starts from it.
- Subprocessor list stays short (Render, Postmark, HIBP, search provider) —
  a product property, not just an ops convenience (LAUNCH-PLAN §0 #1).
- The single-worker constraint (in-process connector rate buckets, B-6) is
  compatible with Render's worker model: exactly one instance, documented
  where it's enforced.
- Costs land at ~$90–175/mo run-rate (LAUNCH-PLAN §8), inside a
  pre-seed-shaped budget (PRD §17.5).

## Revisit triggers

GO verdict (planned migration) · >500 active users · SOC 2 kickoff ·
any Render incident affecting data durability · KMS requirement from
counsel or a B2B design partner.
