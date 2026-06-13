# ADR 0004 — Self-view liveness polling: two-tier audit (immutable chain for exposure, operational log for status), deferred to the async cutover

- **Status:** Accepted — *policy decided now; implementation staged to the async/Celery cutover (see Revisit triggers). No backend code changes ship with this ADR.*
- **Date:** 2026-06-13
- **Context:** The E5 adversarial review (commit `488f605`) confirmed an
  audit-load finding worth deciding before any real async, multi-user
  deployment. The frontend `ScanPanel` polls `GET /scans` every 2s while a
  scan is active, and the report/dashboard read `GET /scans/{id}/findings`
  and `/activity`. Each of those endpoints writes one immutable, hash-chained
  audit row via `record_data_access` →
  [`append_audit_record`](../../backend/ayin/safety/audit.py), which takes
  `SELECT pg_advisory_xact_lock(0x41594E_01)` on the audit chain
  ([audit.py:104](../../backend/ayin/safety/audit.py)). **Every audited read
  therefore serializes on one global lock — the same lock the running
  pipeline uses for its own `scan.*` lifecycle writes.** So an in-flight scan
  with the panel open emits ~1 hash-chain-serialized row/second of *liveness
  re-reads* that contend with the genuine pipeline writes; on the
  async/Celery path with multiple viewers this is the dominant audit cost and
  a lock-contention risk (low-value re-reads stealing lock time from
  high-value lifecycle/exposure writes).

  E5 already cut the **client-side amplification** (partial `/findings` and
  `/activity` fetched only on a progress/status transition, not every tick;
  polling pauses on `visibilitychange`) and deliberately did **not** weaken
  the audit floor — it flagged the core question here instead.

  The core question is a product/contract decision, not a bug: **should a
  user's liveness poll of their *own* scan status write an immutable,
  hash-chained row each time?** CLAUDE.md #4/#7 and PRD FR-TS-1 / §289 / §902
  ("audit coverage must be 100%") make auditing every *subject-data access*
  load-bearing and non-negotiable. But `GET /scans` returns scan **process /
  status metadata** (status enum, job counts) — not the subject's exposed
  PII — and the *meaningful* facts (that a scan exists and when it ran) are
  already immutably recorded once as `scan.created` / `scan.started` /
  `scan.completed`. A liveness poll re-reads data the chain already holds.

## Decision

**Adopt a two-tier access log (Option 2), with an allowlist-shaped boundary
that defaults to the immutable chain. Decide it now; implement it at the
async/Celery cutover.** Until that cutover the live path is
`scan_execution=inline` ([config.py:63](../../backend/ayin/config.py)) and
single-viewer, so the contention is **latent, not active**, and E5's
client-side mitigations bound it. Shipping a new table + migration + retention
timer before the path that needs it would pull Phase-1 work forward against
CLAUDE.md ("don't pull Phase 2+ work forward"; "smallest change").

**The boundary rule (default-immutable, mirrors the `_ACTIVITY_EVENTS`
double-allowlist already in `scans.py`):**

- **Immutable, hash-chained, lock-serialized tier (unchanged — FR-TS-1):**
  *every* scan lifecycle event; *every* read that returns subject **exposure
  content** — `GET /findings` (incl. its `detail.count`, which leaks how much
  is exposed), `/score`, `/report`, `/checklist`, and vault reads; and **all
  staff access and all future non-self (T1+) access, unconditionally.** These
  never qualify for the operational tier.
- **Operational access log (new — append-only, *no* hash chain, *no* advisory
  lock, shorter retention):** the high-frequency self-view reads that return
  only scan **status/process metadata** — `GET /scans`, `GET /scans/{id}`,
  and the `GET /scans/{id}/activity` trail. Still recorded, still queryable,
  still append-only — just off the serialized chain.

A read is on the immutable chain **unless** its `(endpoint, resource)` pair is
on an explicit operational allowlist. New endpoints are immutable by default.

### Options weighed

| Option | Verdict | Why |
|---|---|---|
| **1. Transition-sample** the immutable write (one row per scan-status transition) | Folded in | Already approximated client-side by E5. **Insufficient alone:** still writes to the chain, still takes the global lock. Becomes a cheap optional volume knob *on the operational log* after the split. |
| **2. Split the log** (immutable = exposure + scans + staff; operational = liveness/status) | **Chosen** | Removes lock contention from the hot path *and* is the principled line: the immutable chain protects *exposure of subject data*; status re-reads are operational metadata the chain already records once via `scan.*`. Split ≠ delete — both tiers are append-only and retained, so coverage stays 100% (§902), two-tier by sensitivity. |
| **3. Push (SSE/websocket)** so liveness never hits the audited REST path | Complementary, deferred | Best UX and cuts the reads at the source, but it changes *transport*, not *audit policy* — a pushed state-read still needs a tier decision. Reduces operational-log volume later; doesn't answer the question now. |
| **4. Read-before-write throttle** (skip a duplicate `(actor,resource,scan_id,purpose)` row within N s) | Rejected | Adds a `SELECT` + a read-before-write race on the hot path, and still takes the lock when it does write. Most band-aid-like; the index it needs is better spent on the operational table. |

## Consequences

- **The non-negotiables hold.** 100% of genuine subject-data exposure, every
  scan, and all staff/non-self access stay on the immutable, tamper-evident,
  `verify_chain`-able log. What moves off the chain is re-reads of status the
  chain already records. Nothing becomes *unrecorded* — the safety floor is
  not weakened or made a paid upsell (CLAUDE.md #4). "Audit coverage 100%"
  (§902) stays true; it becomes two-tier by sensitivity, not partial.
- **Lock relief where it counts.** The per-second liveness loop stops
  competing with the pipeline's own `scan.*` writes for `0x41594E_01`, so
  genuine lifecycle/exposure audit latency no longer degrades under viewer
  load.
- **Interim posture (holds until the trigger):** `scan_execution=inline` +
  single viewer means no live contention today; E5's transition-gating +
  hidden-tab pause keep amplification bounded. This ADR is the decision; the
  code is staged.
- **Implementation plan (at the async cutover):**
  1. `operational_access_log` table — append-only via trigger like
     `audit_records`, but **no** `prev_hash`/`hash` chain and **no** advisory
     lock; indexed on `(subject_id, scan_id, occurred_at)`. Shorter retention
     (e.g. 30–90d), pruned by the existing scheduled-jobs beat (LAUNCH-PLAN
     B-7), and decided **with counsel alongside the Phase-1 scan-retention
     decision** that B-7 already defers.
  2. `record_operational_read()` helper beside `record_data_access()`, plus
     the explicit `(endpoint, resource)` allowlist.
  3. Reroute `list_scans`, `get_scan`, `get_activity` → operational log; leave
     `get_findings` / `get_score` / `get_report` / `get_checklist` / vault on
     the immutable chain.
  4. Tests: a non-allowlisted read must land on the immutable chain;
     staff/non-self are never downgradable; the operational log is append-only
     and its retention prunes; `verify_chain` stays green after the hot path
     stops writing to it.
  5. Optional follow-ons: transition-sampling (Option 1) as a volume knob on
     the operational log; SSE (Option 3) to cut the reads at the source.
- **`/activity` is the judgment call.** It returns the user's own scan
  *process* telemetry (planner reasoning, LLM/guard events), not their exposed
  PII, so it sits in the operational tier here — but the conservative default
  (keep it on the immutable chain) is acceptable if counsel prefers; the
  allowlist makes that a one-line move either way.

## Revisit triggers

Async/Celery cutover (`scan_execution=celery`) — **implement at this point** ·
any multi-viewer scenario reaching production · counsel requiring liveness
metadata to be immutably chained (then keep it on the chain and solve
contention via lock-free chaining / partitioning instead of a split) ·
audit-table write latency or `pg_advisory_xact_lock` wait time appearing in
metrics · the Phase-1 scan-retention decision (LAUNCH-PLAN B-7), which the
operational-log retention should be set alongside.
