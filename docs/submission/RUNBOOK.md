# Submission runbook — Ayin (Qwen Cloud Hackathon, Track 4)

Do these in order. Commands are copy-paste. Each step is tagged **[YOU]** (only you can — account/console/recording), **[ME]** (I can do once unblocked), or **[YOU+ME]**.

- **Hard deadline:** July 9, 2026, 2:00 pm PT. **Submit by July 7** (two-day buffer; Devpost gets flaky near deadlines).
- **Repo:** https://github.com/juniper-tc02e/ayin · **License:** AGPL-3.0 · **`main` HEAD must stay the clean MVP.**
- **Already done:** Workstreams A (public repo), B (Qwen integration, validated on Qwen Cloud), E (demo surface), D1 (architecture diagram), the D asset drafts in `docs/submission/`, and the **deploy-hardening pass** (celery task wiring fixed, worker connector bootstrap, `DEMO_MODE` auto-seeds the judge account + enables the synthetic source, editable-install-on-`:ro` bug fixed — 275 backend tests green).
- **One residual unknown** (flagged ⚠): the stack can't be run end-to-end without an actual ECS box (no Docker locally), so the **first live boot is the real test**. The wiring is reviewed + unit-tested; budget a little time on the box for first-boot surprises.

---

## Phase 0 — credentials (≈5 min) **[YOU]**

**The hackathon voucher is OPTIONAL — the whole submission runs without it.** Two separate credit pools cover everything, and neither needs the voucher:
- **Qwen Cloud (the LLM):** your Model Studio account already has a **free quota (~70M tokens)** — a full scan is ~2.5k tokens, so the demo period won't dent it. The $40 voucher is just extra credits on top of that. Eyeball the quota at https://home.qwencloud.com/benefits.
- **Alibaba ECS (the box):** its **own ~$90 free-trial credits**, separate from the voucher (which is Qwen-Cloud credits and can't pay for ECS anyway).

1. *(Optional — skip it)* Voucher form: console avatar → **Account ID** → https://www.qwencloud.com/challenge/hackathon/voucher-application.
2. **Confirm Qwen Cloud creds are in hand** at `%LOCALAPPDATA%\ayin-secrets\` (the day-one cloud call already used them):
   - the API key (`sk-ws…`)
   - the **workspace-scoped** base URL: `https://<workspace>.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`
   - ⚠ Use the **workspace** URL, not the generic dashscope URL `deploy.sh` defaults to. Never commit either.

> **Staying up through July 31 — the real cost risk is the ECS credits, not the voucher.** Use the smallest instance, check the **Billing** console each time you touch the box, and top up a few dollars if the free-trial credits would lapse before judging ends (Jul 31).

---

## Phase 1 — deploy to Alibaba Cloud ECS **[YOU provision · ME hardens first]**

> ✅ **Deploy-hardening done.** `docker-compose.prod.yml` is fixed (celery worker registers its tasks + bootstraps connectors; non-editable install works against the `:ro` mount), and `DEMO_MODE=true` makes the API container **auto-seed the judge account and enable the synthetic source on boot** — so a fresh deploy comes up with `demo-ayin@example.org` logged-in-able and producing findings, no manual seed step. ⚠ Still unrun on a real ECS box — watch the first boot.

### 1a. Provision the instance **[YOU]**
- **ECS**, region **Singapore (ap-southeast-1)**, Ubuntu 22.04, smallest x86 that fits (2 vCPU / 4 GB, ~`ecs.e-c1m2.large`), 40 GB disk.
- **Security group** inbound: **22 (your IP only), 80, 443**. Nothing else.
- *(Optional, nicer cert)* point a cheap domain's A-record at the instance. Bare IP also works (Caddy internal CA).
- Check the **Billing** console — confirm credits cover it; you'll leave it up through July 31.

### 1b. Deploy **[YOU]** (run on the instance)
```bash
ssh root@<ecs-ip>
git clone https://github.com/juniper-tc02e/ayin.git
cd ayin/infra/alibaba

# First run — pass the WORKSPACE base URL + key (from %LOCALAPPDATA%\ayin-secrets\).
# deploy.sh generates all other secrets server-side into .env (chmod 600, never committed).
PUBLIC_HOST=<domain-or-ecs-ip> \
QWEN_BASE_URL='https://<workspace>.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1' \
QWEN_API_KEY='sk-ws…' \
QWEN_MODEL=qwen-plus \
./deploy.sh
```
Later updates are just `./deploy.sh` (keeps the existing `.env`).

### 1c. Verify **[YOU]**
```bash
curl -s https://<host>/api/health            # expect status ok (db ok; redis ok)
docker compose -f docker-compose.prod.yml logs -f api   # watch a scan run
```
Then in a browser: log in as `demo-ayin@example.org` / `ayin-demo-password-1` (auto-seeded), run a scan, open the report — confirm the score, the ✦ Qwen narrative with working citation chips, and "How Ayin ran this scan" all render.

### 1d. Production hygiene (C6) **[YOU]** — before sharing the URL
- [ ] `curl https://<host>/api/health` green; a full scan completes end-to-end
- [ ] `BETA_INVITE_REQUIRED=true` (judges use the demo account, not signup)
- [ ] Demo account auto-seeded + scannable (`DEMO_MODE=true`; scans only its own verified identifiers against the synthetic source — no real PII)
- [ ] Rate limits on (5 scans/day default); abuse heuristics active
- [ ] **`VAULT_MASTER_KEY` backed up off-box** (losing it crypto-shreds every vault payload)
- [ ] Billing checked; instance set to stay up **through July 31**

---

## Phase 2 — record the assets **[YOU]**

1. **Demo video** (<3 min, public YouTube, no copyrighted music). Follow [video-script.md](video-script.md). **Pre-warm the demo scan once before recording** (first `/report`+`/checklist` generate synchronously). 1080p, clean browser, dark theme, slow cursor on the citation-chip click.
2. **Alibaba proof clip** (separate, short): Alibaba console showing the running instance **+** a live `curl https://<host>/api/health` succeeding — one take. (Rules require this in addition to the demo video.)
3. **Blog post** (optional, $500): publish [blog-post.md](blog-post.md) to Medium / dev.to / your site. Keep the public URL.

---

## Phase 3 — fill the submission text **[ME]** (after deploy + recording)

Once you give me `<LIVE_URL>`, the demo creds, and `<VIDEO_URL>` / blog URL, I fill the placeholders in:
- [devpost-description.md](devpost-description.md) → `<LIVE_URL>`, `<VIDEO_URL>`, blog URL, Alibaba proof-clip link
- [testing-instructions.md](testing-instructions.md) → `<LIVE_URL>`
…then commit + push so the repo copies match what you paste into Devpost.

---

## Phase 4 — Devpost form **[YOU]** (paste from our docs)

| Field | Source |
|---|---|
| Project name + tagline | [devpost-description.md](devpost-description.md) |
| Track | **Autopilot Agent** |
| Public repo URL | https://github.com/juniper-tc02e/ayin — verify the **About sidebar shows "AGPL-3.0 license"** (required badge) |
| Alibaba Cloud proof | link `infra/alibaba/deploy.sh` + `backend/ayin/llm/client.py` **and** attach the proof clip |
| Architecture diagram | attach `docs/architecture-diagram.png` |
| Video URL | your YouTube link |
| Text description | [devpost-description.md](devpost-description.md) — includes the "built during the submission window" statement |
| Testing instructions + demo creds | [testing-instructions.md](testing-instructions.md) |
| Blog post URL | optional |

---

## Phase 5 — final hygiene + submit **[YOU+ME]**

1. **[ME] Secret scan `main`** before any final push:
   ```bash
   git --no-pager log --all --name-only --pretty=format: | sort -u | grep -iE "\.env$|secret|credential|\.pem|\.key"
   git grep -iE "(api_key|secret_key|password)\s*=\s*['\"][A-Za-z0-9+/]{16,}" $(git rev-list --all)
   ```
   (Workspace URL + `sk-ws…` must appear **nowhere** in history.)
2. **[YOU] Submit on Devpost by July 7.** Verify every Phase-4 row.
3. **[YOU+ME] Freeze `main`.** Post-deadline edits to the submission aren't allowed — after submitting, any further work goes on a branch, `main` stays as submitted.
4. **[YOU] Through July 31:** instance stays up and free for judges; check Billing periodically; don't touch the submitted repo state. Winners ~Aug 7.

---

## Quick status board

| Workstream | State |
|---|---|
| A — public repo, AGPL, tag | ✅ done |
| B — Qwen integration (planner, narrative+guard, remediation, ER assist) | ✅ done, validated on Qwen Cloud |
| E — demo surface (E1–E5) | ✅ done, verified live |
| D1 — architecture diagram | ✅ done (`docs/architecture-diagram.png`) |
| D2/D3/D4/D5 — video, description, testing, blog | ✍️ drafted; record + publish + fill URLs |
| C — ECS deploy | 🔧 hardened (wiring fixed, demo auto-seeds); ⏳ provision + first live boot |
| Voucher | ⏭️ optional — skippable (Qwen free quota + ECS free-trial credits cover it) |

*Phase-2 "SuperAyin" work is parked on the `superayin-phase2` branch — keep it off `main` until after submission.*
