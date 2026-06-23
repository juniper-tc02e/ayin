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
`consent_t1_enabled` is turned on in prod:

1. **Subject-side revocation (HIGH).** A login-less subject can't authenticate,
   so today only the owner-account or the requester can revoke — which is not
   subject control. Ship a tokened one-click email revoke link (in the ask and
   the on-accept confirmation).
2. **Request-time exclusion/minor screening (HIGH).** `request_consent` must
   check the target against the exclusion + protection lists and silently no-op
   (never reveal protection status); `accept_consent` must run the minor
   heuristics and refuse to mint, not just refuse the eventual scan.
3. **Don't mutate a pre-existing real account via the accept side-door (MED).**
   Seed handles as *unconfirmed* / require the subject to confirm per-handle;
   never auto-VERIFY an existing user's email through a third-party-initiated flow.
4. **One effective grant + honest revoke (MED).** Revoke ALL active grants for
   `(subject, requester)`, always audit the revoke attempt, and revoke even an
   already-expired row.
5. **T1 result-delivery model (MED).** Default decision: **results belong to the
   subject; the requester is never shown another person's findings** (only a
   "scan completed" confirmation). The requester read path stays closed.
6. **Throttle + anti-phishing on the public token endpoints (MED/LOW).** Per-IP
   limits on view/accept/decline; strip URLs from `purpose`; anti-phishing notice
   + report-abuse affordance on the consent page.

- **Still out of scope:** requester identity-proofing beyond an Ayin account
  (e.g. SingPass/org verification).

## Verification

`backend/tests/test_consent_gate.py` (8) — gate verdict for self / no-consent /
valid / revoked / expired / non-adult / excluded-wins / requester-specific.
`test_consent_flow.py` (11) — request→accept→revoke flips the gate; bright-line
refusals; single-use; existing-user attach; request rate-limit/dedupe caps.
`test_consent_api.py` (6) — the HTTP flow end-to-end + the scan endpoint's 403 on
a stranger + the flag-off surface 404. Full suite 367 passed; frontend typecheck
+ build green.
