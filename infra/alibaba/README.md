# Ayin on Alibaba Cloud — hackathon deployment (Workstream C)

This directory is the **Alibaba Cloud proof** the hackathon rules require
(a code file demonstrating Alibaba Cloud use, linked in the submission) and
the runbook for the single-ECS deploy. Status: **scaffolding written ahead of
the account existing — validate end-to-end during C2 before recording the
proof clip.**

The deployed architecture is honestly "Qwen Cloud + Alibaba Cloud":
the backend runs on **ECS**, and `QWEN_BASE_URL` points at **Qwen Cloud's
OpenAI-compatible endpoint** (DashScope intl), which drives the scan planner,
grounded narrative, remediation guidance, and ER assist.

## Provisioning (once)

1. **ECS instance** — Singapore region (`ap-southeast-1`), smallest x86 type
   that fits the stack (2 vCPU / 2–4 GB, e.g. `ecs.e-c1m2.large`-class burst
   instance), Ubuntu 22.04, 40 GB disk. Budget: the $40 voucher + free trial
   credit; check Billing alongside every deploy check (handover risk list).
2. **Security group** — inbound 22 (your IP only), 80, 443. Nothing else;
   Postgres/Redis are never published (see `docker-compose.prod.yml`).
3. **(Nice)** a cheap domain A-record → the instance, so Caddy gets a real
   Let's Encrypt cert. A bare IP works too (Caddy internal CA).

## Deploy / update

```bash
ssh root@<ecs-ip>
git clone https://github.com/juniper-tc02e/ayin.git && cd ayin/infra/alibaba
PUBLIC_HOST=<domain-or-ip> QWEN_API_KEY=<key> ./deploy.sh   # first run
./deploy.sh                                                  # updates
```

`deploy.sh` generates all production secrets **on the server** on first run
(`.env`, chmod 600) — nothing secret is ever committed. The API container
runs `alembic upgrade head` on boot. Re-running the script is safe.

## Production hygiene checklist (C6 — before sharing the URL)

- [ ] `curl https://<host>/api/health` green; a full scan completes
- [ ] `BETA_INVITE_REQUIRED=true` confirmed (signup needs an invite; judges
      use the demo account from the submission's testing instructions)
- [ ] Demo account seeded **with the founder's own verified identifiers
      only** (self-scan rule holds in the demo too — CLAUDE.md #1)
- [ ] Rate limits on (5 scans/day default); abuse heuristics active
- [ ] `VAULT_MASTER_KEY` backed up off-box (losing it = crypto-shred)
- [ ] Billing console checked; leave the instance running **through July 31**
- [ ] Proof clip recorded (C5): Alibaba console showing the instance + a live
      `curl` against the API, one take

## Known gaps (accepted for the hackathon)

- Dev-style images (`pip install -e` on boot) instead of built images —
  production Dockerfiles are a Phase-1 item; first boot is slow, restarts fast.
- No MinIO/object storage on this box (vault payloads live in Postgres via
  the DbVault path; artifact storage is Phase 1).
- Email is console-fallback unless SMTP creds are provided — the judge flow
  uses the pre-seeded demo account precisely so email delivery is not on the
  critical path.
