# Ayin Launch Plan — deployment, backend, frontend, beta

The MVP is code-complete (BUILD-PLAN M0–M5 all shipped: 188 tests, migrations
0001–0014, the §13.7 instruments built). This plan covers the distance between
"code-complete" and "a measured private beta": **deployment**, **backend
hardening**, **frontend/brand**, and the **beta program** itself.

Companions: [`BUILD-PLAN.md`](BUILD-PLAN.md) (what was built),
[`BETA-RUNBOOK.md`](BETA-RUNBOOK.md) (week-to-week operations),
[`Ayin-PRD-and-SaaS-Plan.md`](Ayin-PRD-and-SaaS-Plan.md) (source of truth),
[`adr/0002-deployment-platform.md`](adr/0002-deployment-platform.md) (platform
decision). Constraints: [`../CLAUDE.md`](../CLAUDE.md) — unchanged and binding.

Ticket IDs: **D** deployment · **B** backend · **F** frontend · **T** beta
program. Effort: S (≤½ day) · M (1–2 days) · L (3–5 days). Same usage as
BUILD-PLAN: work the critical path, one ticket per Claude Code session where
possible, per-ticket commits.

---

## 0. What "aligned with the product image" means here

Five principles from the PRD bind every choice below. Each ticket carries an
*Alignment* note tying back to these.

1. **Trust is the product** (PRD §5.5, §15.4). The deployment itself is a
   privacy statement: a short, named subprocessor list; no third-party
   trackers, fonts, or CDNs in the app; first-party analytics only.
2. **Calm, not alarmist** (PRD §12.1). Brand, copy, and even error messages
   stay measured. Marketing never fear-mongers; the landing page sells
   clarity, not panic.
3. **The safety floor is never off** (CLAUDE.md #4, PRD §16.4). No beta
   shortcut may bypass audit, exclusion, deletion, rate limits, or gates.
   Feature flags can gate *features*, never *safeguards*.
4. **Counsel gates sources** (PRD §11.4, §19). Connector governance flags
   (`counsel_signoff`) flip only with recorded review. Where the founder
   accepts interim risk, that acceptance is *written down* (ADR), not implied.
5. **Minimize what we keep — everywhere** (PRD §20.4). Logs, error trackers,
   backups, and analytics follow the same no-PII discipline as the database.
   Backups must not quietly defeat crypto-shred (see D-8).

**The decision rule (PRD §20.5) applies to launch work too:** anything that
would help a watcher more than a self-protector doesn't ship.

---

## 1. Critical path

```
T-1 Counsel engagement ──────────────┐ (longest lead time — start FIRST)
                                     ├─→ governance flags → full connector set
D-1..D-6 Deploy rail (staging→prod) ─┤
B-1..B-5 Hardening + review CLI ─────┼─→ WAVE 0 (founder + friendlies,
F-1..F-3 Brand, landing, privacy ────┤    counsel-light config, §5.1)
T-2..T-4 Cohort + comms prep ────────┘
                                          ↓ fixes + counsel sign-offs land
                                     WAVE 1 (15 users) → WAVE 2 (+25)
                                          ↓ weeks of T-5..T-7 rituals
                                     T-9 go/no-go (python -m ayin.beta.gonogo)
```

Sequencing rules:
- **T-1 starts before anything else** — counsel lead time (2–3 weeks) is the
  long pole. Everything else proceeds in parallel.
- Wave 0 does NOT wait for counsel: it runs the **counsel-light source
  configuration** (§5.1) — licensed APIs under their standard commercial
  terms, broker page-probing OFF.
- Wave 1 requires: wave-0 bug list closed, restore drill done (D-10), review
  CLI live (B-2), privacy policy published (F-3), counsel verdict on HIBP +
  search terms (or a written founder risk acceptance, ADR'd).
- Broker probing enables **per broker**, only after counsel reviews the
  method memo AND that broker's probe is live-verified (B-4).

---

## 2. Deployment plan (D)

Platform: **Render** (decision + alternatives in ADR-0002). Two environments,
`staging` and `production`, in a US region (US-first launch, PRD §22.3).

### D-1 — Production container images (M)

Today's compose installs deps at boot (dev-only). Build real images:

- `backend/Dockerfile`: multi-stage — builder installs into a venv from a
  **locked** requirements file (B-5); runtime on `python:3.12-slim`, non-root
  `ayin` user, `PYTHONDONTWRITEBYTECODE=1`, healthcheck hitting `/health`.
  Entrypoints (same image, different commands):
  - api: `uvicorn ayin.api.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips '*'`
  - worker: `celery -A ayin.orchestrator.celery_app:celery_app worker -B -l info --concurrency 1`
    (concurrency 1 is deliberate for beta — see B-6 rate-limiter constraint)
  - release: `python -m alembic upgrade head` (Render preDeploy)
- `frontend/Dockerfile`: Next.js `output: "standalone"`, non-root, port 3000.
- Image hygiene: `.dockerignore` (no tests/docs/.git), trivy or grype scan in
  CI (D-6), images tagged with the git SHA.

*Accept:* both images build in CI; `docker run` of each passes its
healthcheck locally; image scan has no criticals.
*Alignment:* #5 — images contain no fixtures, no .env, no docs.

### D-2 — Render blueprint: services + datastores (M)

`render.yaml` (infrastructure-as-code lite; Terraform deferred to Phase 1):

| Service | Type | Plan (beta) | Notes |
|---|---|---|---|
| `ayin-api` | web service (Docker) | Starter | autoscale OFF (predictability), health `/health` |
| `ayin-worker` | background worker (Docker) | Starter | exactly **1 instance** (B-6) |
| `ayin-web` | web service (Docker) | Starter | Next.js standalone |
| `ayin-pg` | managed Postgres 16 | Basic + PITR | daily backups, 7-day retention (see D-8) |
| `ayin-redis` | managed Key Value | Starter | Celery broker + future rate-limit store |

- Staging mirrors production at the smallest sizes; **previews disabled**
  (ephemeral copies of a PII database are exactly what we don't do).
- Object storage (MinIO locally) is **not provisioned** for beta — nothing
  writes raw artifacts yet (vault holds sensitive payloads in Postgres).
  Revisit at Phase 1 alongside the orchestrator's artifact work.
- MailDev is dev-only; production email is Postmark (D-5).

*Accept:* `render.yaml` deploys both environments from the repo; staging
auto-deploys `main`, production deploys on a manually-approved tag.
*Alignment:* #1 — every service named here appears in the subprocessor list (F-3).

### D-3 — Domain, TLS, edge security (S)

- Domain (e.g. `ayin.app` — placeholder until purchased): apex → `ayin-web`,
  `api.` → `ayin-api`. Render-managed TLS certificates.
- Backend middleware additions (small code change, part of B-1):
  HSTS (`max-age=31536000; includeSubDomains`), `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  strict-origin-when-cross-origin`, conservative CSP on the app
  (`default-src 'self'`; Next inline-style allowance documented).
- CORS pinned to the production web origin only (already config-driven via
  `WEB_BASE_URL`); `COOKIE_SECURE=true` (production boot already refuses
  without it — `config.assert_production_safe`).
- Render's per-service request limits + our own app-level rate limits remain
  the throttling story; a WAF is Phase-1.

*Accept:* SSL Labs A; securityheaders.com A; cookies `Secure; HttpOnly;
SameSite=Lax`; CORS rejects foreign origins.

### D-4 — Secrets management + rotation runbook (S)

- Render env groups per environment: `APP_SECRET` (48+ random bytes),
  `VAULT_MASTER_KEY` (32-byte base64 via `openssl rand -base64 32`),
  `BREACH_API_KEY`, `SEARCH_API_KEY`, `POSTMARK_TOKEN`,
  `BETA_INVITE_REQUIRED=true`, `SCAN_EXECUTION=celery`, `APP_ENV=production`.
- **Honest tradeoff, recorded:** Render has no KMS; the vault master key
  lives as an env var. Mitigations for beta scale: the key never appears in
  logs (logging policy test, D-7), env access limited to the founder's
  account with 2FA, rotation procedure below, and the **Phase-1 migration to
  AWS KMS is a committed item** on the GO path (T-9). ADR-0002 records this.
- Rotation runbook (`docs/runbooks/rotate-secrets.md`, written with this
  ticket): APP_SECRET rotation invalidates sessions + step-up tokens (users
  re-login — acceptable; announce in-app); VAULT_MASTER_KEY rotation requires
  a re-wrap job (decrypt each `vault_keys.wrapped_dek` with old, wrap with
  new — small script, write + test it in this ticket BEFORE it's ever needed
  under pressure).
- Staging and production share **nothing**: separate keys, separate Postmark
  server tokens, separate invite codes.

*Accept:* runbook exists and the re-wrap script has a test; secrets appear
nowhere in the repo, images, or logs (gitleaks in CI, D-6).

### D-5 — Transactional email: Postmark (M)

Four flows send mail today via SMTP/console (`ayin/services/email.py`):
account verification, identifier verification, exclusion confirmation —
plus beta comms (T-4) sent manually.

- Postmark over SMTP-API on a dedicated transactional stream;
  `no-reply@<domain>` sender; DKIM + SPF + DMARC (`p=quarantine` to start).
- `PostmarkEmailSender` implementing the existing `EmailSender` protocol
  (B-3); per-message tags (`account-verify`, `identifier-verify`,
  `exclusion`) for deliverability triage; bounces checked in the weekly
  ritual (T-5).
- Deliverability matters disproportionately: verification links ARE the
  product's front door, and exclusion links are a *rights* mechanism — a
  bounced exclusion confirmation is a compliance problem, not a growth
  problem. Monitor the exclusion tag's delivery rate explicitly.
- Why Postmark: transactional-only reputation, no marketing features to
  misuse, minimal data retention settings, clean subprocessor story (#1).

*Accept:* all three flows deliver to mainstream inboxes from staging;
DMARC passes; suppression list empty at wave-1 start.

### D-6 — CI/CD: GitHub Actions (M)

Pipeline on every PR + main:

1. `ruff check` + `mypy ayin`
2. `pytest` (pgserver-backed — the suite needs no services) split into the
   four groups already used in practice, parallel jobs
3. frontend: `tsc --noEmit` + `next build`
4. supply chain: `pip-audit` against the lockfile, `npm audit --omit dev`,
   `gitleaks` (secrets), trivy on built images
5. **alignment guard**: the scripted audit from the M5 chore commit
   (Settings ⊆ .env.example, single alembic head, route uniqueness, ToS
   version consistency, FakeConnector-never-prod, allowlisted analytics
   events) promoted into `backend/tests/test_alignment.py` so drift fails CI
   forever — this catch already paid for itself once.

Deploys: staging on merge to `main` (Render auto-deploy); production on a
`v*` tag with manual approval; `alembic upgrade head` as preDeploy with an
automatic Render backup snapshot beforehand. Rollback = Render redeploy of
the previous image (migrations are additive-only by policy during beta —
no destructive downgrades).

*Accept:* a PR with a failing alignment check cannot merge; tag-to-prod
takes one approval; a deliberately broken canary deploy rolls back cleanly
on staging.

### D-7 — Observability without PII (M)

The observability stack follows the same discipline as the database:

- **Structured JSON logs** (uvicorn + app loggers) with a written logging
  policy: log ids and counts, never identifier values, finding payloads, or
  tokens. Enforced by a unit test that exercises hot paths with a canary
  email/phone and asserts they never reach log output (`test_logging_policy`,
  part of B-1).
- **No third-party APM/error SaaS for beta.** Render logs + log search, an
  uptime monitor on `/health` (staging + prod), and a daily error-grep in
  the ops ritual cover 50 users. Sentry-class tooling becomes a Phase-1
  decision with scrubbing requirements written first. (#1: every avoided
  subprocessor is one less line in the privacy policy.)
- **COGS visibility (PRD §17.2):** `connector_jobs.cost_usd` already
  accumulates per job — add the weekly COGS query to the Monday ritual
  (T-5) and a soft budget alert: if daily summed cost exceeds
  `CONNECTOR_DAILY_BUDGET_USD`, log loudly + email the founder (simple beat
  task; hard auto-disable guards are Phase 1).
- **Safety telemetry:** weekly `verify_chain` beat task alerting on failure
  (B-7); the §18.4 T&S metrics (refusals, holds, exclusions honored, audit
  coverage) queried in the Monday ritual — these are board-level numbers
  even when the board is one person.

*Accept:* logging-policy test green; uptime alerts reach the founder's
phone; one week of ritual entries exists before wave 1.

### D-8 — Backups, restore, and the crypto-shred tension (M)

Managed Postgres gives daily snapshots + PITR. But **backups can quietly
defeat crypto-shred**: a snapshot taken before a shred still contains the
subject's wrapped key. Policy, written into the privacy page and the
runbook:

- Backup retention **7 days** for beta (≤ the 30-day vault retention; short
  by design).
- The restore runbook's **first mandatory step after any restore**: replay
  shreds and exclusions executed after the snapshot — both are reconstructable
  from the immutable audit log (`vault.shredded` and `exclusion.confirmed`
  events carry subject ids), and account deletions likewise
  (`account.delete_requested`). Write `scripts/replay_rights.py` with a test:
  restore-sim → replay → shredded subject's vault items unreadable again.
- Quarterly (and once before wave 1): full restore drill on staging from a
  production-shaped synthetic snapshot, timed, with the replay step.

*Accept:* `replay_rights.py` tested; drill performed and timed; privacy
policy states backup retention and the replay guarantee in plain language.
*Alignment:* #5 — "delete everything" means everywhere, including yesterday's
snapshot once it's restored.

### D-9 — Staging data policy (S)

Staging contains **synthetic data only**: FakeConnector enabled, fake
accounts, staging-only invite codes, `noindex` headers, separate Postmark
sandbox stream. Production data is never copied down — debugging uses
synthetic reproductions. (The only exception: the restore drill in D-8 uses
a synthetic production-shaped snapshot, never the real one.)

*Accept:* a documented staging-reset script; spot check shows zero real
emails in staging.

### D-10 — Launch-day runbook + smoke suite (S)

`docs/runbooks/deploy.md`: tag → approve → preDeploy migration → smoke.
Promote the ad-hoc e2e curl sequence used throughout the build into
`scripts/smoke.sh` (signup w/ invite → verify → ToS → preview → scan →
score/checklist/findings → step-up unlock → intent → exclusion request →
delete-everything; asserts on status codes and key fields) — run against
staging in CI nightly and against production right after every deploy
(with a dedicated smoke invite + immediate self-deletion, which also
exercises delete-everything in prod weekly).

*Accept:* `scripts/smoke.sh staging` green in CI; post-deploy prod smoke
documented in the runbook and leaves no residue (the smoke account
self-deletes — verified by the script).

---

## 3. Backend plan (B)

No new product features — the MVP scope holds. This is hardening, the one
genuine operational gap (B-2), and live-source verification.

### B-1 — Production server posture (M)

- Uvicorn multi-worker behind Render's proxy: `--proxy-headers`, trusted
  hosts middleware pinned to the api hostname, request body limit (1 MB is
  generous for this API), sensible timeouts, gzip for JSON.
- Security headers middleware (D-3's list) + structured JSON logging config
  with the no-PII logging policy test (`tests/test_logging_policy.py`:
  drives signup/scan/findings with canary values, asserts captured log
  records never contain them).
- `/health` gains `migration_rev` (current alembic head) so deploy smoke can
  assert code↔schema match — no secrets, no counts.
- Login brute-force guard: small per-email+IP counter on `/auth/login`
  failures (5/15min → 429 with calm copy), mirroring the existing
  rate-limit pattern. (OTP attempts are already capped; signup enumeration
  via 409 stays for beta — documented tradeoff, revisit with counsel.)

*Accept:* logging-policy test green; headers verified; lockout works and
audits `auth.login_failed` spikes into an `AbuseSignal` (reuses M1-6's
hammering pattern).

### B-2 — T&S review CLI — the real gap (M)

The beta promises a 48-hour appeal SLA (BETA-RUNBOOK) but today a HELD scan
has no release path and appeals have no resolution tooling. Build
`python -m ayin.safety.review`:

- `list` — open AbuseSignals + held scans, oldest first, SLA clock shown
- `show <signal-id>` — full context: heuristic detail, scan status, history
  (never raw identifier values in terminal output beyond what's needed —
  reviewer sees kinds + heuristic, requests values only when necessary via
  an explicit `--unmask` that writes a `data.access` audit record)
- `release <scan-id> --note ...` — staff-actor audited; re-runs gates with
  the tripped heuristic suppressed for this scan, then dispatches normally
  (the scan still passes *all other* gates — release is not a bypass of the
  floor, it overrides exactly one false-positive heuristic)
- `refuse <scan-id> --note ...` — finalize refusal with reviewer note
- `resolve <signal-id> --status actioned|dismissed --note ...`
- `protection add|remove --kind X` — prompts for the value, stores only the
  hash (the value never hits argv/history), audited as staff action

*Accept:* a held scan can be released end-to-end in tests (gate → hold →
release → done with findings); every action writes staff-actor audit
records; SLA clock visible in `list`.
*Alignment:* #3 — review tooling strengthens the floor (appeals work);
release is single-heuristic, never a gate bypass.

### B-3 — Postmark sender + email templates (S)

`PostmarkEmailSender(EmailSender)` selected by config (`EMAIL_PROVIDER=
postmark|smtp|console`); shared plain-text-first templates with one calm
visual wrapper; the three existing flows route through it untouched
(the `EmailSender` protocol already isolates this). Console fallback stays
hard-refused in production (existing behavior — verify with a test).

### B-4 — Connector live verification tooling (M)

The mocked-transport tests prove the contract; before real users, verify
the live edges — without writing any real result data:

- `scripts/verify_connectors.py`: HIBP smoke against its documented
  test accounts (key validity, 404-clean path, 429 handling with one
  retry); search API smoke with an obviously-synthetic quoted string
  (asserts shape, not content); prints per-connector PASS/FAIL + measured
  latency (feeds honest ETAs in `/scans/preview`).
- `python -m ayin.connectors.broker.verify --broker <id> --name "Fake
  Person" --city "Faketown"`: fetches that broker's probe URL for a
  synthetic name, reports robots verdict, HTTP status, which found/notfound
  markers matched, and a content snippet — the evidence row for enabling
  that broker. Results recorded as dated comments in `registry.yaml`.
  Target: 10 verified brokers for wave 2 (counsel permitting).
- Run cadence: before each wave and monthly (brokers drift).

*Accept:* both tools run clean against staging config; ≥10 broker
verification records exist before any probe enables; ETA constants in
`preview.py` updated from measured latencies.

### B-5 — Supply chain + security pass (M)

- **Pin everything:** generate `backend/requirements.lock` (pip-compile)
  from `pyproject.toml`; Docker builds use the lockfile; `package-lock.json`
  already pins the frontend. Renovate/Dependabot weekly with CI as the gate.
- `pip-audit`/`npm audit` clean or triaged; `gitleaks` clean.
- OWASP pass (checklist in `docs/runbooks/security-review.md`): authz on
  every subject resource (isolation tests already exist — extend to the
  newer endpoints), IDOR sweep of all `{id}` routes (404-not-403 posture is
  already the convention), SSRF surface review (the broker prober fetches
  registry-defined URLs only — no user-supplied URLs anywhere; assert with
  a test), token TTLs, header check, dependency CVEs.
- Threat-model refresh (1 page, `docs/runbooks/threat-model.md`): assets =
  vault keys, audit chain, identifier values; adversaries = stalker-user
  (gates), external attacker (hardening), curious operator (audit on staff
  access); residual risks named — env-var master key (D-4), email
  enumeration (B-1).

*Accept:* CI runs the supply-chain jobs; review checklist completed and
dated; threat model committed.

### B-6 — Capacity + the single-worker constraint (S)

Beta math (50 users, 5 scans/day cap): worst-day ≈ 250 scans ≈ 750
connector jobs — trivial for one worker. The real constraint is the
**in-process token bucket** (M0-7): per-connector budgets are only honest
with one worker process. Decision for beta: **run exactly one worker
instance with `--concurrency 1`** (D-1/D-2 pin this) and document it in the
worker Dockerfile. The Redis-backed bucket is a committed Phase-1 item on
the GO path. HIBP's 10 rpm tier comfortably covers wave sizes (3 emails ×
50 users staggered by the queue); `verify_connectors.py` confirms real
limits before wave 1.

*Accept:* constraint documented where it's enforced (Dockerfile + compose +
render.yaml comments); a load smoke (20 concurrent scan starts on staging)
completes without rate-limit violations from our side.

### B-7 — Scheduled-jobs verification + data lifecycle (S)

Beat already schedules `resume_stalled` (60s) and `vault.purge_expired`
(hourly). Add `audit.verify_chain` weekly (alert on failure) and the COGS
budget check (D-7). Verify all four fire in staging (log evidence) — a beat
that silently isn't running is how retention promises rot. Scan-history
pruning: explicitly **not** pruned during beta (history feeds the funnel +
QA); decision on long-term scan retention goes to the Phase-1 list with
counsel.

*Accept:* staging logs show each scheduled task firing on cadence; a
deliberately-broken chain in staging triggers the alert path.

### B-8 — Beta configuration seeding (S)

Production seed checklist (executed via runbook, not ad hoc): rate-limit
policy row reviewed (5/day, burst 2 — keep), wave-1 invites generated and
logged in the beta journal, protection-list intake path documented (DV-org
partnership entries if/when they exist — hashes only), `ProtectionEntry`
and `Exclusion` tables empty-verified at start (no test residue).

---

## 4. Frontend plan (F)

The app works; this track makes it *feel* like the product the PRD
describes — calm, trustworthy, accessible — and gives the beta a public
face. No SPA rewrites; the design tenets (PRD §12.1) are already encoded in
`frontend/README.md` and partially in `globals.css`.

### F-1 — Brand foundation (M)

- **Name story:** *ʿayin* — "eye." The mark: a minimal geometric eye/aperture
  glyph that reads as *seeing*, never as *watching* (no CCTV/spy tropes —
  the brand is the user's own clear sight). Wordmark in the UI font for
  beta; commissioned identity is post-GO.
- **Design tokens:** formalize the existing CSS variables into a documented
  scale (`frontend/styles/tokens.css`): semantic names
  (`--color-positive/--caution/--alert` over ok/warn/down), spacing + type
  scale, score-band colors (single source shared with ScorePanel).
  **Contrast-check every pair** (feeds F-5; current `--warn` on `--surface`
  is borderline).
- **Typography:** self-hosted Inter via `next/font/local` — no external
  font CDN (#1).
- **Voice guide** (`docs/brand/voice.md`, one page): calm, second person,
  verbs not nouns, no fear-mongering, no exclamation marks in errors;
  exposure is described as *fixable state*, never *threat theater*. Examples
  rewritten from real strings (error messages, empty states, emails).
- Favicon + OG image set (landing only; app pages are noindex).

*Accept:* tokens file used by all components (no stray hex values —
lint-able via grep in CI); voice guide exists with ≥10 before/after pairs.

### F-2 — Public landing page (M)

Today's landing is a stack status card. The beta needs a front door that
matches §15.4 messaging:

1. Hero: **"See what the internet knows about you — then make it forget."**
   Sub: self-scan only, sourced findings, one clear score. CTA: invite-code
   entry (gate-aware via `/config`) + "No invite? → hello@<domain>"
   (no waitlist database for beta — one less store of emails; the inbox IS
   the waitlist).
2. How it works, 3 steps: verify it's you → we check breaches, the public
   web, data brokers → fix it with a ranked plan. Real (synthetic-data)
   report screenshot.
3. **Trust section — the differentiator, above the fold-fold:** what we keep
   (findings + score) and don't (raw dossiers, plaintext secrets); every
   access audited; "Exclude me from Ayin" linked prominently (not only the
   footer); delete-everything is one click; short subprocessor list linked.
4. FAQ: the FCRA line in plain language ("Ayin is not a background check —
   it can't be used for hiring, tenancy, credit, or insurance, and we
   enforce that"); "could someone scan me?" (no — verified self-scan only,
   plus exclusion); "what does the score mean?" (data exposure, not a
   judgment of you); pricing honesty ("the scan is free; monitoring and
   removal are coming — the report has a waitlist").
5. Footer unchanged (exclude/terms) + privacy policy link (F-3).

*Accept:* Lighthouse ≥95 (performance/a11y/SEO) on the landing; zero
third-party requests in the network panel; copy passes the voice guide.
*Alignment:* #2 — the page sells clarity and control; the trust section is
the pitch, exactly as §15.4 prescribes ("our safety posture is marketing").

### F-3 — Privacy policy + subprocessor page (M, counsel-reviewed)

Draft now (so counsel reviews instead of writes — cheaper): what we
collect and why (per identifier kind), retention table (vault 30d, backups
7d + replay guarantee from D-8, findings/score until deletion, audit
trail's no-PII design), the named subprocessor list (Render, Postmark,
HIBP, search provider — what each sees), rights (access via
/account/summary, deletion, exclusion — with the actual flows linked, not
just described), US-first scope statement, contact. Written in the product
voice: short sentences, no legalese wall; the legalese version can live
beside it.

*Accept:* page live before wave 1; counsel sign-off recorded (or founder
interim acceptance ADR'd per T-1); every claim in it is true of the code
(cross-check against tests — e.g. retention numbers match `Settings`).

### F-4 — App UX polish pass (M)

Beta-blocking only (everything else → backlog):

- Resend buttons for account/identifier verification (the dead-end today
  if an email is missed); session-expiry → clean redirect to login with a
  calm message; global error boundary + 404 with recovery links.
- Scan progress: per-source rows with the *why* from `/scans/preview`
  (reuse), partial-findings count, and a gentle skeleton — no spinners
  that imply something is wrong.
- Mobile audit at 360px: report tables → stacked cards; tap targets ≥44px;
  the step-up modal usable on-screen-keyboard.
- Dev-only copy ("MailDev at :1080") rendered only when
  `/config` says invite gate off AND env is dev — strip from production.

*Accept:* a phone-only run of the full journey (signup → report → review →
delete) succeeds without zooming or dead ends.

### F-5 — Accessibility to WCAG 2.1 AA (M)

A privacy product's audience includes exactly the people most often
excluded by inaccessible security tooling.

- Contrast: fix token pairs to ≥4.5:1 (notably warn-on-surface).
- Keyboard: focus rings on the dark theme, focus trap + ESC in StepUpModal
  and the delete-confirm flow, skip-to-content link.
- Semantics: landmark roles, form labels (several inputs rely on
  placeholder today — F-4 overlaps), `aria-live` for scan progress updates
  and score changes, button vs link hygiene in FindingsList.
- `prefers-reduced-motion` respected (progress bars, transitions).
- Automated axe checks inside the Playwright suite (F-7) + one manual
  screen-reader pass (NVDA) of the report.

*Accept:* axe: zero serious/critical on all routes; manual pass notes filed.

### F-6 — Production build + privacy tech posture (S)

`output: "standalone"`; `X-Robots-Tag: noindex` on app routes (landing,
terms, privacy, exclude indexable); CSP from D-3 verified against Next's
needs; **zero third-party origins** asserted by a Playwright test that
fails on any non-first-party request (the test IS the policy, #1);
`trackClient` (first-party analytics) documented on the privacy page.

### F-7 — Playwright e2e suite (M)

Real-browser journeys against staging (nightly) + a smoke subset in CI:

1. invite signup → email verify (MailDev API on staging) → ToS → seeds →
   preview → scan → report → score visible
2. possible-match review: confirm → score rises; reject → falls
3. credential lock → step-up unlock → breach detail visible
4. checklist expand → opt-out link present (action_started fires)
5. intent CTAs → joined state persists on reload
6. exclusion: request → confirm → re-login → scan refused with the honest
   `subject_excluded` message
7. delete-everything → login impossible → re-signup clean
8. invite gate: no/invalid/exhausted code paths
9. axe scan on every visited route (F-5)

*Accept:* suite green nightly on staging two consecutive weeks before
wave 1; flake rate <2%.

### F-8 — Deliberate restraints (S, documentation)

Named non-features for beta, recorded so they're decisions rather than
omissions: no public report share-links (leak vector; P1 ships expiring
redacted exports per FR-REPORT-2), no PDF export, no social-share of
scores (despite §15.2 referral ideas — referral mechanics wait until they
can be designed privacy-safe), no third-party sign-in (Google OAuth stays
env-gated off), no chat widgets. Each gets one line of *why* in the
backlog.

---

## 5. Beta program plan (T)

Expands BETA-RUNBOOK.md from a cadence sheet into a full program. The beta's
single question (PRD §13.1): *will a non-technical person give us
identifiers, get an accurate sourced picture, understand the score, act —
and want ongoing protection?*

### T-1 — Counsel engagement (M effort, LONG lead — start first)

- **Find:** fractional privacy counsel with FCRA/CCPA + data-broker
  experience (referrals from privacy-eng communities, IAPP directory).
  Budget: a scoped fixed-fee review, ~$3–6k.
- **Scope pack** (assemble in this ticket so the engagement starts on day
  one; most of it already exists in-repo):
  1. ToS/AUP draft (`frontend/app/terms/page.tsx`) + AUP enforcement design
  2. Privacy policy draft (F-3) + retention/backup-replay design (D-8)
  3. HIBP commercial license terms + our usage pattern
  4. Search API commercial terms + our usage pattern
  5. **Broker probe method memo**: robots-respecting fetch of public listing
     pages, identifying UA, detect-to-remove purpose, per-broker enablement —
     ask specifically about ToS-conflict risk per §11.1's "without violating
     the source's terms" test
  6. Data-broker registration analysis (CA/TX/OR/VT) per §19.2
  7. FCRA controls review (§19.3) — the AUP language + purpose enforcement
- **Interim risk posture if counsel is slower than the calendar** (founder
  decision, recorded as ADR-0003 when taken): HIBP + search are standard
  commercial APIs used within their published terms → acceptable for wave 0
  with the governance flag flipped under a written founder acceptance;
  **broker page-probing stays OFF without counsel, no exceptions** — it's
  the one source with real ToS ambiguity, and the product still
  demonstrates 2 of 3 categories without it.

*Accept:* engagement letter signed OR ADR-0003 records the interim
posture with reasoning and a counsel deadline; scope pack delivered.

### T-2 — Wave 0: founder + friendlies (week 1 post-deploy; 3–5 people)

- Counsel-light config (§T-1); invites tagged `wave-0`.
- Objectives: full-journey bug bash on real devices; timing data for honest
  ETAs; copy comprehension (watch one person read their report cold — say
  nothing, take notes); **concierge augmentation** (PRD §13.9): the founder
  manually checks every wave-0 finding against its cited source — this
  doubles as the first real QA sample through `ayin/qa`.
- Exit criteria to wave 1: zero data-integrity bugs; all blocking UX issues
  fixed; smoke + Playwright green on prod config; restore drill done (D-8);
  review CLI live (B-2); privacy policy published (F-3).

### T-3 — Cohort recruiting + screening (M)

- **Channels** (trust-led, per §15.2 — no ads): personal network and its
  second ring; privacy/security communities where giving value first is the
  norm (carefully, per each community's self-promo rules); 1–2 privacy
  newsletter authors offered early access for honest feedback (not coverage);
  if a DV/anti-stalking org relationship exists, *advisory* input on the
  exclusion/protection flows — at-risk users are NOT beta fodder (#3).
- **Screener** (form): scanning yourself only? (hard requirement,
  consent checkbox) · 18+ · US-resident · persona fit (P1 privacy-anxious /
  P2 post-breach / P3 online-visible) · device mix · interview willingness.
  Target mix: ~50% P1, ~25% P2, ~25% P3 across 40 accepted.
- **Waves:** wave 1 = 15 (weeks 2–5) → iterate → wave 2 = +25 (weeks 6–9),
  full source set if counsel has signed off; measurement close weeks 10–12.

*Accept:* screener live; ≥30 qualified screeners before wave-1 invites go
out (over-recruit for no-shows); persona mix tracked in the journal.

### T-4 — Comms templates (S) — `docs/beta-comms/`

invite (consent recap + what Ayin is/isn't — includes the FCRA line and
self-scan-only rule) · welcome (what to expect, how to read the score,
support contact) · week-2 nudge (re-scan + review your "possible matches" —
drives the M2 review loop and the action metric honestly, not dark-pattern-ly)
· interview ask · incident notice (hopefully unsent) · close-out (thanks +
delete-everything offer + what's next). All in the F-1 voice; all plain
text; unsubscribe honored manually (one inbox, 50 people).

### T-5 — Measurement rituals (S, then weekly discipline)

Codified in BETA-RUNBOOK (already) + journal templates in
`docs/beta-journal/` (`week-NN.md`: funnel numbers, T&S metrics per §18.4
— refusals/holds/exclusions-honored/audit-coverage —, COGS, QA precision,
bounce check, top 3 user quotes, decisions made). Monday: `make funnel
days=7` + T&S queries. Wednesday: QA sample (n=50 or all-new findings,
whichever is smaller). Biweekly: `make gonogo qa=...` dry run so the final
read has trend context. The journal is the institutional memory the go/no-go
meeting reads.

### T-6 — Interview program (M across the beta)

12–15 interviews (every wave-0 user + ~⅓ of each wave), 25 min, recorded
with consent, guide per BETA-RUNBOOK §interview (aha / score comprehension
**including the FCRA-line check** — if anyone says "trustworthiness," copy
fixes ship that week / action friction / trust gaps / willingness-to-pay
calibrated against §16 price points). Synthesis template per interview;
weekly rollup into the journal keyed by pseudonymous user_ref.

### T-7 — Support + accuracy-dispute ops (S)

- `support@<domain>`: 24h response SLA, founder-staffed; canned-but-warm
  responses aligned to the voice guide.
- **Accuracy disputes are a first-class flow** (PRD §19.1 defamation row):
  user flags a finding → reviewer checks the cited source → if wrong,
  suppress via review tooling + note → feeds the next QA sample and, if
  systematic, a connector fix. Target: resolved ≤72h, tracked in the
  journal. (In-product dispute button is P1; beta uses the confirm/reject
  flow + support for everything else.)
- Appeals (held/refused scans): 48h SLA via the B-2 CLI; every resolution
  audited.

### T-8 — Incident readiness (S)

Before wave 1, run three 30-minute tabletops with the runbooks open:
(1) our-breach scenario — key rotation (D-4 runbook), affected-subject
shred + notify, audit chain as forensic spine; (2) abuse case — hold, B-2
review, ban path, preservation; (3) source cutoff — central disable,
user-facing status note. Fix whatever the tabletop reveals is missing
*then*, not during the real thing.

### T-9 — Go/no-go close-out (S)

Week 12: final `python -m ayin.beta.gonogo --days 90 --qa-reviewed <latest>`
+ the journal + interview synthesis into a one-page decision memo.
- **GO** → Phase 1 kickoff list (pre-staged): monitoring engine (FR-MON-1/2)
  · automated broker opt-outs (FR-REM-1) · DROP/DSAR (FR-REM-2) · billing
  (Plus/Pro per §16.2) · AWS/KMS migration (retires the D-4 tradeoff) ·
  Redis rate-limiter (retires B-6) · SOC 2 groundwork · public free-scan
  launch (§15.5).
- **NO-GO / kill criteria** → per-cause playbook: accuracy-driven → connector
  + ER investment or scope narrowing before any paid build; activation-driven
  → report redesign + concierge round to find the missing aha; demand-driven
  (intent <25%) → pricing/positioning research before engine work.
- **INSUFFICIENT** → extend, don't lower the bar (the instrument refuses to
  flatter small cohorts by design).

### Beta risk register (tracked in the journal; PRD §19.5 lineage)

| Risk | L | Trigger to act | Mitigation |
|---|---|---|---|
| Counsel delay blocks brokers | High | not signed by wave-1 −1wk | counsel-light config (T-1); brokers in wave 2; ADR-0003 |
| Accuracy < 90% (broker/search namesakes) | Med | Wed QA below 90% once | M2 cap already protects auto-merge; tune markers; suppress offending broker; QA weekly catches early |
| Recruiting shortfall | Med | <30 screeners by wave-1 −1wk | over-recruit early; second-ring asks; small thank-you gesture (not payment-for-praise) |
| Email deliverability | Med | verification delivery <95% | D-5 DMARC done early; Postmark tag triage; resend buttons (F-4) |
| HIBP rate ceiling at re-scan bursts | Low | 429s in logs | queue already staggers; nudge emails staggered by cohort halves |
| Real-PII incident in logs/analytics | Low | logging-policy test or audit finds any | D-7/B-1 tests; weekly grep; incident tabletop #1 |
| Founder bandwidth (solo ops) | High | rituals slip 2 wks running | rituals are calendared + scripted (`make funnel/gonogo/qa-sample`); wave sizes chosen for one person; cut wave 2 size before cutting rituals |

---

## 6. Alignment matrix

| Plan item | Product principle / PRD anchor |
|---|---|
| Short subprocessor list; no APM SaaS; first-party analytics only (D-2/D-7/F-6) | Trust is the product (§5.5, §15.4); minimize (§20.4) |
| Backup-restore replays shreds/exclusions (D-8) | "Delete everything" means everywhere (§20.4; FR-TS-3/4) |
| Counsel gates per-source; broker probes off without review (T-1/B-4) | §11.4 governance; §11.1 "publicly available" test |
| Review CLI: release overrides one heuristic, never the floor (B-2) | Safety floor never off (CLAUDE.md #4); FR-SCAN-5 appeal |
| Landing trust section = the pitch; FCRA FAQ in plain words (F-2) | §15.4 "safety posture is marketing"; §19.3 bright line |
| Voice guide bans fear-mongering; calm errors (F-1/F-4) | §12.1 calm-not-alarmist |
| At-risk users advise, are not recruited (T-3) | §20.2 protections for vulnerable people |
| Logging-policy + zero-third-party tests as CI gates (B-1/F-6/D-6) | §20.4 stewardship enforced, not promised |
| Intent CTAs honest ("manual opt-outs work today") (M4-4, T-4 nudges) | §15.4 honest; §16 free tier completeness |
| No share links/exports in beta (F-8) | §20.5 decision rule (leak vector > value, for now) |
| Weekly §18.4 T&S metrics in the journal (T-5) | §18.4 "board-level, not footnotes" |
| ADR for every accepted risk (D-4 env key; T-1 interim posture) | §22.1 decisions recorded, not implied |

## 7. What we deliberately will NOT do for launch

No paid ads or growth hacks; no third-party analytics/pixels/fonts/CDNs in
the app; no waitlist database (an inbox suffices); no public scores or share
mechanics; no payment collection (intent capture only, per §13.3); no
staging copies of production data; no EU launch (US-first per §22.3 —
revisit Phase 2 with GDPR LIA work); no relaxation of any safety-floor
component for "beta convenience"; no shipping broker probes ahead of
counsel.

## 8. Budget (monthly run-rate during beta)

| Item | Est. |
|---|---|
| Render (api + worker + web + Postgres + Redis, staging + prod) | ~$60–90 |
| Postmark (transactional, beta volume) | ~$15 |
| Domain + misc (uptime monitor free tier) | ~$3 |
| HIBP API subscription | ~$4–40 (tier TBD by B-4 verification) |
| Search API (per-call, ~750 jobs/mo worst case) | ~$10–25 |
| **Run-rate** | **~$90–175/mo** |
| One-time: counsel scoped review | ~$3–6k |
| One-time: domain purchase | ~$10–50 |

COGS guard: the D-7 daily budget alert is set to $5/day initially (≈3×
expected worst-case) — alert, investigate, raise deliberately.

## 9. Execution order (suggested Claude Code sessions)

| Session | Tickets | Outcome |
|---|---|---|
| 1 | T-1 scope pack, D-1, B-5 lockfile | counsel engaged; images build; deps pinned |
| 2 | D-2, D-3, D-4 (+ rotate runbook + re-wrap script) | staging live end-to-end |
| 3 | B-1, D-7 (logging policy, headers, health rev, budgets) | hardened api on staging |
| 4 | B-2 (review CLI) + B-3 (Postmark) | appeal SLA serviceable; real email |
| 5 | D-6 (CI/CD + alignment test promotion), D-10 (smoke.sh) | pipeline gates everything |
| 6 | F-1, F-2, F-3 drafts | brand + landing + privacy page on staging |
| 7 | F-4, F-5 | UX/a11y pass |
| 8 | F-7 (Playwright), F-6, D-9 | e2e green nightly; staging policy |
| 9 | B-4 (connector verification), B-6 load smoke, B-7, D-8 drill | sources verified; restore drilled |
| 10 | T-2 wave 0 + fixes; B-8 seeding; T-3/T-4 prep | wave 1 ready |
| 11+ | T-5..T-8 operating rhythm → T-9 | the measured beta |

Definition of done for this plan: wave 1 invites sent with every wave-1
gate in §1 satisfied — and the first Monday journal entry written.
