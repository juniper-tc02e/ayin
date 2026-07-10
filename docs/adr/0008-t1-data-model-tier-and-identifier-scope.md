# ADR 0008 — T1 data model: real scan tier + per-requester identifier scope

- **Status:** Accepted
- **Date:** 2026-06-23
- **Relates:** implements two data-model changes required by the [`ADR-0007`](0007-consent-gated-third-party-scans.md)
  pre-enablement re-audit. Still gated behind `consent_t1_enabled` (off in prod).
- **Implementation:** `backend/ayin/models/{scan,enums,subject}.py`,
  `backend/ayin/orchestrator/engine.py`, `backend/ayin/consent/flow.py`,
  migrations `0020` (identifier scope) + `0021` (scan tier). Branch: `main`.

## Context

An adversarial re-audit of the consent feature (2026-06-23) surfaced two HIGH
findings that are genuine *data-model* gaps, not code bugs — so they get an ADR,
not just a patch:

1. **Scan tier was hard-pinned to self.** The `scans` table CHECK enforced
   `tier = 't0' AND purpose = 'self'`, and `ScanTier` had only `T0_SELF`.
   `create_scan` never set tier/purpose, so *every* consented third-party scan
   was silently recorded as an ordinary self-scan — the schema's own
   "load-bearing" backstop was never engaged for T1, corrupting audit/telemetry.
2. **Consent was authorization-only, never identifier-scoped.** A `ConsentGrant`
   binds `(subject, requester)`, but seeded handles lived subject-wide. If a
   subject confirmed handle X for requester A and later confirmed a different
   handle Y for requester B, A's next scan would fan out to Y too — a handle the
   subject disclosed only to B. Per-requester purpose/scope was violated.

## Decision

### 1. A real T1 tier, tied to purpose (migration 0021)

- `ScanTier` gains `T1_CONSENTED = "t1"`.
- The `scans` CHECK is replaced with one that **ties tier to purpose**:
  `(tier='t0' AND purpose='self') OR (tier='t1' AND purpose<>'self')`. A scan can
  never be recorded as self while targeting someone else.
- `create_scan` sets `tier`/`purpose` from `subject.owner_user_id == requester.id`
  — t0/`self` for a self-scan, t1/`consented` for a third-party scan.
- This *widens* the load-bearing constraint the schema docstring said needs "a
  migration + ADR + counsel review." This ADR is that record; the widening is
  deliberately minimal (adds exactly T1, keeps the tier⇔purpose tie).

### 2. Per-requester identifier scope (migration 0020)

- `Identifier` gains a nullable `consent_requester_id` (FK users, cascade).
  **NULL = the subject's own seed (self-scan, T0)** — unchanged. **Non-NULL = a
  handle the subject confirmed FOR THAT requester** via a consent grant.
- `accept_consent` tags each seeded handle with the requester it was confirmed
  for; the subject's verified email anchor stays NULL (shared identity anchor).
- `eligible_seed_identifiers(db, subject_id, requester_user_id=...)`: when the
  requester is **not** the subject's owner (a third-party scan), the seed set is
  restricted to identifiers with `consent_requester_id == requester` **plus** the
  verified email anchor — never another requester's handles. A self-scan (owner ==
  requester, or the arg omitted) is unchanged. All engine seed-selection call
  sites now pass the scan's requester; the change is backward-compatible so the
  live T0 path is untouched.

## Alternatives / trade-offs

- **Join table for identifier↔requester (many-to-many)** instead of a column:
  rejected for MVP. The single column can *under*-include a handle two requesters
  both confirmed (the `UNIQUE(subject,kind,value)` row is tagged to whoever seeded
  it first, so the second requester's scan won't see it) — a **safe** failure
  (under-scan, never over-scan / leak). A join table is the clean upgrade if that
  edge matters operationally.
- **A trigger tying tier to the subject↔requester relationship** (not just the
  purpose column): stronger, but a column-level CHECK plus the always-on consent
  gate is sufficient for MVP; the gate is what actually prevents non-consented
  scans.

## Consequences

- Third-party scans are now correctly tiered in the DB + audit trail, and a
  requester's scan can only ever touch the identifiers that requester was
  authorized to know. Revoking a grant + the exclusion list still apply on top.
- T0 self-scan behaviour is unchanged (verified by the full suite).
- Still behind `consent_t1_enabled` (off in prod) pending a clean re-audit.

## Verification

`test_consent_flow.py`: third-party scan only sees its own requester's confirmed
handles (`test_third_party_scan_only_sees_that_requesters_handles`); a third-party
scan row is tagged t1/non-self (`test_third_party_scan_row_is_tagged_t1_not_self`).
Orchestrator + preview suites confirm T0 seed selection unchanged. Full suite green.
