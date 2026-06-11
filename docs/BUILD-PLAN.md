# Ayin MVP — Build Plan

The MVP, sequenced into Claude-Code-sized tickets. Scope is **T0 self-scan only** across three categories (breach/credential, public-web/social, data-broker detection) → resolve → score → report → manual remediation guidance, on top of a non-negotiable safety floor. Source of truth: [`Ayin-PRD-and-SaaS-Plan.md`](Ayin-PRD-and-SaaS-Plan.md) §13. Constraints: [`../CLAUDE.md`](../CLAUDE.md).

## How to use this with Claude Code

- Work milestones top to bottom; finish a milestone's tickets before starting the next.
- Each ticket names the **PRD FRs** it satisfies — open the PRD §9 for full acceptance criteria before building.
- Good per-session prompt: *"Read CLAUDE.md and docs/BUILD-PLAN.md. Implement ticket M1-2. Show me the connector contract before wiring the breach source."*
- A ticket is done only when its acceptance bullets pass **and** the CLAUDE.md "definition of done" holds (safety floor intact, findings sourced, audit written, no PII committed).
- The MVP target is ~12 weeks for a small team (PRD §13.8); solo-with-Claude-Code will differ — sequence matters more than the calendar.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done.

---

## M0 — Foundations (PRD weeks 0–2)

Goal: an empty but trustworthy skeleton — a request can authenticate, accept the ToS, and write an audit record, and a fake connector can run behind the contract.

- [x] **M0-1 — Local dev environment.** Docker Compose with Postgres + Redis + MinIO; `.env.example` → `.env`; one `make dev` / task runner entry that boots the stack. Backend (FastAPI) and frontend (Next.js) skeletons run and talk to each other.
  - *Accept:* `docker compose up` brings up all services; API health check green; frontend renders a placeholder landing page.
- [x] **M0-2 — Data model + migrations.** Implement core entities (`User`, `Subject`, `Identifier`, `Scan`, `Finding`, `Score`, `RemediationTask`, `AuditRecord`, `AbuseSignal`) as migrations. (PRD §10.4)
  - *Accept:* migrations apply cleanly; every Finding row requires `source`, `captured_at`, `confidence`, `sensitivity`; Identifier has a `verification_state`.
- [x] **M0-3 — Account creation + auth.** Email/OAuth signup; session/JWT; per-user isolation. (FR-AUTH-1)
  - *Accept:* user can sign up, log in, log out; no cross-user data access.
- [x] **M0-4 — Self-identity verification.** Prove control of each seed identifier before its results are viewable (email link, phone OTP); step-up before any credential-level data. (FR-AUTH-1)
  - *Accept:* unverified identifier cannot surface sensitive results; verification state stored on the Identifier.
- [x] **M0-5 — ToS/AUP gate.** Versioned ToS + Acceptable-Use Policy acceptance recorded with timestamp; scan blocked until accepted; re-prompt on version change. (FR-AUTH-2)
  - *Accept:* first scan is blocked until acceptance row exists; version bump re-prompts.
- [x] **M0-6 — Immutable audit log.** Append-only `AuditRecord` writer used by a thin `record_scan_event()` / `record_data_access()` helper; tamper-evident (hash chain or append-only table + checks). (FR-TS-1)
  - *Accept:* every scan and every subject-data read writes a record; records are not updatable/deletable through the app.
- [x] **M0-7 — Connector contract.** Define the uniform interface every source implements: `authenticate`, `fetch`, `normalize`, rate-limit + backoff, cost telemetry, and a `SourceGovernance` metadata block (legal basis, access method, ToS ref, data classes, cost/call, rate limits, counsel sign-off flag). Ship a `FakeConnector` implementing it. (FR-DISC-4, PRD §11.4)
  - *Accept:* `FakeConnector` runs through the contract and emits normalized Findings with full attribution; a connector cannot be registered without a complete governance block.

## M1 — Discovery (PRD weeks 2–5)

Goal: three real connectors produce sourced findings, driven by a queue-based orchestrator, with sensitive data in the vault.

- [x] **M1-1 — Scan orchestrator (job state machine).** States: `queued → gated → running → resolving → scoring → done | failed | held`; Celery tasks per connector; partial results persisted; resumable/retryable. (PRD §10.1, FR-SCAN-1)
  - *Accept:* a scan fans out to connectors, survives a worker restart mid-run, and records status transitions.
- [x] **M1-2 — Breach/credential connector.** Integrate one HIBP-class breach API; return breach name, date, data classes, exploitability. **Never** store or display full plaintext secrets — exposure status / partial only. (FR-DISC-1)
  - *Accept:* verified email/phone/username returns breach findings with source + confidence; no plaintext credential is ever persisted or rendered.
- [x] **M1-3 — Public-web/social connector.** Compliant search API / public endpoints; capture URL, platform, snippet, captured-at; respect robots/ToS and the "publicly available" definition. (FR-DISC-2, PRD §11.1)
  - *Accept:* returns public profile/mention findings for seeds; nothing behind a login; each finding cites its URL + capture time.
- [x] **M1-4 — Data-broker detection connector.** Detect presence on a hand-curated set of ~20–50 high-impact US brokers; record site, listing URL, exposed fields; flag as removable. **Detect only — no removal in MVP.** (FR-DISC-3, PRD §13.6)
  - *Accept:* detects listings across the seed set; each flagged `removable` with manual opt-out instructions attached.
- [x] **M1-5 — PII vault.** Encrypted, access-controlled store for sensitive findings/artifacts; per-subject keys; retention timers; crypto-shred. All reads go through an audited accessor. (PRD §10.7)
  - *Accept:* sensitive fields are encrypted at rest; reading them writes an audit record; a delete crypto-shreds the subject's keys.
- [x] **M1-6 — Rate/volume enforcement.** Per-account/per-tier caps on scan frequency and burst velocity; clear "you're limited" messaging; limits server-configurable. (FR-SCAN-3)
  - *Accept:* exceeding the cap blocks with a clear message; limits change without a deploy.

## M2 — Resolution + scoring (PRD weeks 5–7)

Goal: merge the user's own identifiers without namesake mixing, and turn findings into one explainable score.

- [x] **M2-1 — Self-identifier entity resolution.** Rules + thresholds over the user's *own verified* identifiers; no auto-merge of low-confidence records; user can confirm/reject. (FR-ER-1, FR-ER-2)
  - *Accept:* same-person records merge above threshold; below-threshold shown as "possible, unconfirmed"; false-merge rate measured in tests.
- [x] **M2-2 — Dedupe + classify + attribute.** Deduplicate findings; classify by category + sensitivity; flag conflicting data rather than silently merging. (FR-ER-2, PRD §23.2)
  - *Accept:* duplicates collapse with sources preserved; every finding has category + sensitivity.
- [x] **M2-3 — Exposure Score v0 + rubric.** 0–100 overall + category sub-scores (Credentials, Brokers, Social, Records, Linkage), weighted by sensitivity × exploitability × recency × corroboration; versioned rubric; each point traces to findings. (FR-SCORE-1, PRD §8.3, §23.3)
  - *Accept:* score recomputes per scan; tapping a contributor shows the findings; rubric version is labeled; measures exposure only (no character/eligibility signal).

## M3 — Report + safety (PRD weeks 7–9)

Goal: the activation moment — a calm, sourced report — plus the rest of the safety floor.

- [x] **M3-1 — Exposure report UI.** Hero score + one-line plain-language verdict; "top 3 to fix now"; findings by category (what / where / captured-when / source / confidence / action); graceful empty/low-exposure states. Calm, not alarmist. (FR-REPORT-1, PRD §12.1, §23.4)
  - *Accept:* a completed scan renders the full report skeleton; low-exposure users see a reassuring state, not a blank page.
- [x] **M3-2 — Hardening checklist (read-only).** Per-finding steps (rotate password, enable MFA, revoke sessions, lock down profile) with expected score impact. Read-only in MVP; tracking is Phase 1. (FR-REM-3 lite)
  - *Accept:* each high-impact finding has actionable steps with an expected score delta.
- [x] **M3-3 — Abuse refusal + safety hold.** Refuse/hold scans matching abuse heuristics (minor-subject signals, victim-protection match, anomaly flags); log reason; appeal path. (FR-SCAN-5, FR-TS-2)
  - *Accept:* a scan tripping a heuristic is refused/held with a logged reason; false-positive appeal path exists.
- [x] **M3-4 — "Exclude me from Ayin" (public).** Verify identity → suppress as scan subject → purge cached data; honored on future scans; linked from the footer, not buried. (FR-TS-3, PRD §12.2 Flow D)
  - *Accept:* an excluded identity is suppressed in subsequent scans and its cached data purged; action audited.
- [x] **M3-5 — Data-subject rights + delete-everything + retention.** Self-service "delete my account and all data" (crypto-shred); retention timers auto-purge raw artifacts. (FR-TS-4)
  - *Accept:* delete-everything removes/shreds all subject data and confirms; retention job purges raw artifacts on schedule.

## M4 — Polish + instrument (PRD weeks 9–11)

Goal: make the funnel measurable and the findings trustworthy.

- [x] **M4-1 — Onboarding + seed entry.** Multi-identifier entry (name, emails, phones, usernames, city) with validation/normalization; "here's what we'll check and why" + ETA; async progress with partial results streaming in. (FR-SCAN-1, PRD §12.2 Flow A)
  - *Accept:* a non-technical user can enter seeds and watch progress to a report.
- [x] **M4-2 — Analytics instrumentation.** Track the AARRR funnel for the §13.7 metrics: scan-started, scan-completed, report-viewed, action-started, monitoring-intent captured. Privacy-respecting (no PII in events).
  - *Accept:* each metric in §13.7 is queryable; no PII leaves the app in analytics payloads.
- [x] **M4-3 — Findings-accuracy QA harness.** Sampling + manual-QA workflow to measure precision on shown findings against the ≥ 90% target; track false-merge rate. (PRD §13.7, §18.3)
  - *Accept:* a repeatable harness reports finding precision and ER false-merge rate on a sample.
- [x] **M4-4 — Monitoring/removal intent capture.** Waitlist/pre-order CTA on the report ("watch for new exposure", "remove these listings") measuring pull without building the engine. (PRD §13.2)
  - *Accept:* intent is captured per user and reportable as a % of activated users.

## M5 — Private beta & go/no-go (PRD weeks 11–12)

- [ ] **M5-1 — Invite-only beta** for a recruited cohort (self/consented subjects only).
- [ ] **M5-2 — Measure against go/no-go criteria** (PRD §13.7) and interview users.

### Go / no-go to Phase 1 (PRD §13.7)

| Metric | Target |
|---|---|
| Scan completion (start → report) | ≥ 70% |
| Activation (report viewed + understood) | ≥ 55% |
| Findings precision (sampled, manual QA) | ≥ 90% |
| ≥ 1 remediation action started | ≥ 40% of activated |
| Monitoring/removal intent (waitlist/pre-order) | ≥ 25% of activated |
| Safety: zero non-self scans; 100% of scans audited | hard gate |

**Kill criteria:** if accuracy can't clear ~90% without heroics, or activation stalls below ~35% after iteration, rethink the wedge before building the paid engine.

---

## Explicitly NOT in the MVP (PRD §13.3 — don't build these yet)

Any non-self scan (T1–T3), org accounts, SSO, API · automated broker removal, DROP/DSAR automation (capture intent only) · continuous monitoring/alerting · public records, image search, technical/attack-surface modules · identity-graph visualization, exports, B2B dashboards · full billing (a simple founding/pre-order plan to test willingness-to-pay is optional).

## Optional pre-MVP de-risker (PRD §13.9)

Run 25–50 **manual "concierge" scans** for recruited users (analyst assembles the report by hand in Ayin's format) to validate accuracy, report design, the "aha," and willingness-to-pay before automating — and to seed the broker playbook and scoring rubric. Self/consented subjects only, same safety rules.
