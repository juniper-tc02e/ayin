# ADR 0007 — Consent-gated third-party scans (T1): the subject is the only one who can authorize

- **Status:** Accepted — gate deployed always-on; T1 user-facing **surface flag-gated OFF**
  in prod (`consent_t1_enabled`) pending the pre-enablement follow-ups below.
- **Date:** 2026-06-23
- **Supersedes/relates:** extends the gate/orchestrator model ([`ADR-0001`](0001-architecture-and-mvp-scope.md));
  the consented footprint runs the same engine as [`ADR-0006`](0006-username-footprint-connector.md).
- **Implementation:** `backend/ayin/consent/` (model, store, flow), the gate in
  `backend/ayin/orchestrator/engine.py` (`run_gates`), routes in
  `backend/ayin/api/routes/consent.py`, UI in `frontend/components/ConsentManager.tsx`
  + `frontend/app/consent/page.tsx`. Branch `feat/consent-gate`.

## Context

Ayin's MVP is self-scan only (CLAUDE.md #1). The legitimate next tier (PRD §20.5,
T1) is **scanning someone who has consented** — a security team protecting an
exec, a person they're lawfully responsible for. The danger is obvious: the same
machinery, pointed at a non-consenting person, is stalkerware. The §20.5 decision
rule asks whether we can *verify the requester, bound the purpose, rate-limit it,
audit it, and let subjects exclude themselves*. The hard part is making consent
**real** — not a checkbox the requester ticks on the subject's behalf.

A request to "build third-party scanning" was explicitly declined in its
build-everything-first-restrict-later form. This ADR records the consent-first
design that was built instead.

## Decision

**Consent is a structural precondition enforced at the gate, and it can only be
created by the subject's own verified action.** Concretely:

1. **The gate refuses by default.** `run_gates` refuses any scan where
   `subject.owner_user_id != scan.requester_user_id` unless
   `consent.store.active_consent(...)` returns a live grant. This check sits
   **after** the exclusion check (exclude-me always wins) and **before** any
   seed selection or dispatch, so no connector ever runs against a
   non-consenting subject. `active_consent` is the single source of truth;
   no partial validity check is inlined anywhere else.

2. **A grant is verified, time-bound, revocable, scoped, adult-attested.** The
   `ConsentGrant` row is valid only while `revoked_at is null`,
   `granted_at <= now < expires_at`, and `adult_attested is true`. Revocation is
   effective immediately (the next `active_consent` returns `None`).

3. **Only the subject can mint a grant.** The flow (`ayin.consent.flow`) is:
   the requester *asks* (`request_consent`) — naming the subject by **their own
   email** and a bounded purpose; a single-use link token is delivered to that
   address. Possession of the link proves the subject controls the email (same
   basis as identifier email-verification). The subject reviews the ask and,
   attesting they are 18+, **accepts** (`accept_consent`) — which verifies their
   email, seeds the handles they confirmed, mints the grant, and writes the
   audit record **with the subject as actor**. There is deliberately **no**
   function, route, or UI path that lets a requester self-assert a subject's
   consent.

4. **Bright lines preserved.** No minors (acceptance without adult attestation
   is refused, not recorded). Publicly-available sources only (the consented
   scan runs the same self-scan engine — ADR-0006 — never private accounts or
   auth bypass). Full audit: `consent.requested` (actor = requester),
   `consent.granted` / `consent.revoked` (actor = subject). The link is
   single-use and itself time-bound.

## Alternatives considered

- **Requester attests consent (a checkbox / uploaded authorization).** Rejected:
  it makes consent a claim by the *attacker-shaped* party. The whole safety
  property is that the subject, not the requester, is the source of truth.
- **Require the subject to be a pre-registered Ayin user.** Too much friction and
  not necessary: email-link possession already proves control. A subject who
  isn't a user is created as a **login-less record** (`password_hash` NULL),
  reachable only through consent links — they exist as a subject-of-record, not
  an account.
- **Build the scan path first, add restriction later.** Explicitly rejected
  (the safety core must precede any cross-subject execution, and it did — the
  gate + tests landed before the flow and the endpoints).

## Consequences

- A whole tier (T1) becomes possible without weakening T0: self-scan is entirely
  unaffected (gate short-circuits when requester == owner).
- **The gate ships and deploys live always-on** — it can only ever *refuse* more
  scans, so it is a pure safety improvement to the running site. The **T1
  user-facing surface** (request/accept/revoke endpoints + UI, and the
  `POST /scans {subject_id}` path) is gated behind `consent_t1_enabled`, which is
  **OFF in production**. With it off, `/consent/*` 404s and the UI hides itself;
  this does not rely on prod's (currently inert) SMTP for safety.

### Pre-enablement follow-ups (from the 2026-06-23 adversarial audit)

An adversarial pre-deploy audit (a workflow of finders + a completeness critic)
found that the feature shipped the *authorize* half without a complete, safe
*deliver / revoke / screen* half. These MUST land and re-pass the audit before
`consent_t1_enabled` is turned on in prod. **All six are now implemented (behind
the flag); a re-audit is the last gate before flipping it on.**

1. **Subject-side revocation (HIGH). — DONE.** `accept_consent` mints a single-use
   revoke-token hash (`consent_grants.revoke_token_hash`, migration 0018); the
   on-accept confirmation email carries a one-click `/consent/revoke?token=` link,
   and `POST /consent/revoke/{token}` (public) revokes with no login. The frontend
   `/consent/revoke` page POSTs on click (email prefetch can't trigger it).
2. **Request-time exclusion/minor screening (HIGH). — DONE.** `request_consent`
   now screens the target (email + proposed handles) against the exclusion +
   victim-protection lists and the minor heuristics, and **silently no-ops** on a
   match (no row, no email, no reason — an indistinguishable "pending" response,
   audited as `consent.request_screened` with only a generic class).
   `accept_consent` re-screens and **refuses to mint** (and to verify the email /
   seed handles) on a match. Reuses the exact scan-gate safety logic
   (`safety.abuse.screen_subject_identifiers` + `safety.exclusion.split_excluded`).
3. **Don't mutate a pre-existing real account via the accept side-door (MED). —
   DONE.** `accept_consent` only verifies the email + seeds handles for a
   login-less record it created (`user.password_hash is None`); a pre-existing
   real account is never mutated by the third-party-initiated flow (its scan
   simply needs its own verified anchor).
4. **One effective grant + honest revoke (MED). — DONE.**
   `store.revoke_all_active` revokes EVERY not-yet-revoked grant for the
   `(subject, requester)` pair (so a duplicate live grant can't survive), even an
   expired-but-unrevoked one; `flow.revoke_consent` always audits the attempt with
   a count. The authenticated revoke endpoint no longer no-ops on an expired grant.
5. **T1 result-delivery model (MED). — DONE.** Decided: **results belong to the
   subject; the requester is never shown another person's findings.** The scan
   read endpoints stay owner-scoped (a requester 404s on a consented subject's
   scan — regression-tested); the requester UI now shows a "scan started, results
   go to them" confirmation instead of routing to a report.
6. **Throttle + anti-phishing on the public token endpoints (MED/LOW). — DONE.**
   `safety.ip_throttle.IpRateLimiter` caps the unauthenticated token endpoints
   (view/accept/decline/revoke) per IP; `flow._sanitize_purpose` strips link-shaped
   text from `purpose`; the consent page carries an anti-phishing notice +
   report-abuse mailto.

- **Still out of scope:** requester identity-proofing beyond an Ayin account
  (e.g. SingPass/org verification).

### Re-audit remediation (2026-06-23)

A second adversarial audit of the "done" blockers found the surface still wasn't
enable-ready: 1 critical + 6 high. All were remediated (flag still OFF):

- **Screening oracle (CRIT) — fixed.** The old silent-no-op was distinguishable
  (response-code, timing, unsanitized-purpose echo). Now request creation ALWAYS
  writes a rate-limit-counting row with a `screened` flag (migration 0019), the
  email is a `BackgroundTask` (timing-independent) sent only for non-screened
  targets, and the response is the real row's sanitized value → indistinguishable.
- **Revoke gated by the flag (HIGH) — fixed.** Only request *creation* is behind
  `consent_t1_enabled`; view/accept/decline/revoke are always reachable.
- **`POST /scans` leaked the subject's results (HIGH) — fixed.** Redacted to a
  bare confirmation when the target isn't the requester's own subject.
- **Scan tier mislabelled / identifier scope subject-wide (HIGH ×2) — fixed in
  [`ADR-0008`](0008-t1-data-model-tier-and-identifier-scope.md).**
- **Throttle neutralized behind the proxy (HIGH) — fixed.** uvicorn now runs with
  `--proxy-headers` so the limiter keys off the real client IP (each IP its own
  bucket; an attacker can't 429 everyone). The in-memory limiter is per-worker
  (≤2× budget) — a shared Redis store is the noted upgrade.
- Mediums/lows: URL/shortener strip widened; revoke audit attribution +
  always-audit; revoke-token bounded to its grant's life; no PII in delivery logs.

**Documented residuals (not blocking; low exploitability / need a product call),
to revisit before scale:** grant `scope="footprint"` is recorded but connector
selection isn't yet scope-limited; a login-less consent subject can't later claim
that email for a real account; the per-target harassment cap is per-account (prod
mitigates via invite-only signup); `POST /scans` does no route-layer relationship
check (the orchestrator consent gate is the real enforcement).

## Verification

`backend/tests/test_consent_gate.py` (8) — gate verdicts. `test_consent_flow.py`
(24) — request→accept→revoke flips the gate; bright-line refusals; single-use;
rate-limit/dedupe; exclusion/protection/minor screening; no-account-mutation;
revoke-all + honest-expired revoke; subject revoke-link token; purpose URL-strip.
`test_consent_api.py` (10) — HTTP flow end-to-end; flag-off 404; third-party 403;
revoke-link email works unauthenticated; requester can't read a subject's scan;
public endpoints IP-throttled. Frontend typecheck + build green. Re-audit pending
before `consent_t1_enabled` flips on in prod.
