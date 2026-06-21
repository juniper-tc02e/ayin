# ADR 0006 — Username Footprint: Sherlock's reach inside the self-scan trust model

- **Status:** Proposed
- **Date:** 2026-06-20
- **Supersedes/relates:** extends the connector contract ([`ADR-0001`](0001-architecture-and-mvp-scope.md));
  shares the candidate/anti-namesake lifecycle described in [`ADR-0005`](0005-pivot-graph-data-model.md).
- **Implementation:** `backend/ayin/connectors/username/` (branch `feat/username-footprint`);
  full plan + build prompts in [`docs/plans/username-footprint-connector.md`](../plans/username-footprint-connector.md).

## Context

[Sherlock](https://github.com/sherlock-project/sherlock) (MIT) checks whether a
username exists across 400+ sites. Its headline capability — *"give me any
username and find it everywhere"* — is **third-party enumeration of an arbitrary
person**, which directly violates Ayin's load-bearing constraints: #1 (MVP is
self-scan only) and the §20.5 decision rule (a feature must be more valuable to
someone protecting themselves than to someone targeting another person). Adopting
Sherlock wholesale would turn a privacy tool into stalkerware.

But the *defensive* version of that capability is exactly Ayin's wedge: a person
deserves to know "where does my handle appear publicly, and how do I shrink that?"
The question was how to take Sherlock's **engine** without taking its **threat
model**.

## Decision

**Port Sherlock's detection engine as a self-scan connector; leave its targeting
model behind.** `username_footprint` is a sibling of `broker_detect`: it probes a
small, ToS-reviewed allowlist of public profile pages for the **requester's own
asserted/verified username**, with the full safety floor intact.

What we take from Sherlock (its `data.json` is the derivation source, MIT —
attributed in `sites.yaml` and `tools/sherlock_import.py`):
- the three detection strategies — `status_code` / `message` / `response_url`;
- `regexCheck` charset gating and per-site request shaping (method/headers/body);
- the 400-site knowledge base, but only as **input to a vetting pipeline**.

What we deliberately leave behind: arbitrary targets, Tor / `--unique-tor` / proxy
rotation (block-evasion conflicts with ToS-respect and reads as detection-evasion),
aggressive fan-out, and any wholesale unvetted import.

### The seven structural guarantees

1. **Self-scan only.** `supported_kinds = {USERNAME}`; the scan is gated upstream
   by a verified anchor (FR-AUTH-1) and the orchestrator's exclude-me chokepoint.
   The connector never receives a target it isn't entitled to probe.
2. **ToS-vetting gate.** Every `sites.yaml` row carries a governance block; only
   `tos_status: ok` rows are ever probed (`enabled_sites()`). Sherlock's sites
   enter as `tos_status: unvetted` via `tools/sherlock_import.py` and never hit the
   network until a human/counsel reviews them. The connector's `SourceGovernance`
   carries `counsel_signoff=False`, so it **cannot enable in production** (registry
   gate, PRD §11.4) — it is registered for discovery but disabled.
3. **Honest `unknown`.** Unlike Sherlock's binary claimed/available, detection
   emits `present | absent | unknown`. A block page, throttle, 5xx, transport error,
   or any redirect on a `status_code`/`message` site → `unknown` → dropped, never a
   false "present". This is what protects the ≥90% shown-finding precision floor
   (PRD §13.7); the false-positive-via-redirect class is closed by construction.
4. **Anti-namesake by reuse, not new code.** A username is not control-verifiable,
   so `resolution._match_pass` caps username-keyed findings at 0.65 (< the 0.70
   auto-match threshold): they are **always `POSSIBLE`, never silently merged**
   (FR-ER-1), and only the user's confirmation (or independent corroboration) lifts
   them. The same cap applies to the linkage finding.
5. **Ownership tiers gate sensitive probing.** Tier-0 (asserted) is the default;
   Tier-1 (verified) is an opt-in upgrade. nsfw / high-critical sites probe **only**
   for a verified owner who explicitly opted in for that scan (`_sensitive_allowed`)
   — the floor holds by construction, not by the manifest happening to mark
   sensitive rows non-`ok`. (The Tier-1 verification *mechanism* — bio-code or
   OAuth — is deferred to UF5; the gate is already enforced.)
6. **Good-citizen networking.** robots.txt respected (fail-safe: any robots error
   or ambiguous 401/403/429/5xx → deny; only 404/410 → allowed), an identifying
   `AyinSelfScanBot` User-Agent on every probe, per-host pacing, per-site error
   isolation, and the per-connector token bucket from governance. No evasion.
7. **Exclude-me + minors + audit.** A handle on the exclude-me list is never probed
   (orchestrator chokepoint, plus a fail-loud in-connector check). Minor signals in
   a username already refuse the scan (`safety/abuse._minor_signals`). Every probe
   and finding read is hash-chain audited like any other connector. Sensitive
   payloads route to the PII vault (the `sensitive_payload` seam) — UF5 populates it
   when sensitive sites become probeable.

### Scoring & remediation

Username findings are `category=SOCIAL` and score through the existing rubric once
confirmed. A handle reused across ≥3 sites additionally emits a **`LINKAGE`**
finding — cross-account linkability is its own exposure (one handle lets a stranger
pivot between all your accounts) — capped to `POSSIBLE` like every username finding.
The hardening checklist generates the concrete per-site removal flow from each
site's `opt_out`, plus a "use distinct usernames" linkage item. The B1 grounded
narrative cites these findings with sources like any other; the LLM never authors a
finding (CLAUDE.md #5).

## Consequences

- **Positive:** Ayin gains Sherlock-grade reach *and* what Sherlock lacks — consent,
  scoring, actionable removal, and accountability — while staying a privacy tool.
  Reusing the broker pattern + the existing ER/scoring meant the net-new surface was
  small (a manifest, a detection function, a connector, a linkage rule, a checklist
  branch) with no core-pipeline or schema changes.
- **Cost / debt:** the allowlist is deliberately small (≈15 sites) and grows only
  through review; that's slower than Sherlock's 400 but is the point. Cross-site
  **display-name/avatar corroboration** (which would justify lifting confidence
  above the namesake cap) needs profile enrichment we don't yet capture, so no naive
  handle-count boost is applied — deferred to avoid the namesake trap.
- **Enablement is gated:** the connector ships **disabled**. Turning it on requires
  counsel sign-off on the vetted sites, UF5 (verification) for any sensitive
  category, and UF6 (the UI surface). Until then it runs only in tests.

## Alternatives considered

- **Wholesale Sherlock import (400 sites, as-is).** Rejected: unvetted ToS exposure,
  no consent model, and the binary claimed/available false-positive rate fails the
  precision floor.
- **A new `Candidate`/verification table for username ownership.** Rejected for the
  same reason as ADR-0005: `Finding.match_status` already models the candidate
  lifecycle; a username finding is simply one born `POSSIBLE`.
- **A distinct `username_footprint` score category (DB enum + migration).** Rejected:
  `SOCIAL` already weights by sensitivity + corroboration, and `LINKAGE` already
  exists for the cross-account-linkability signal — no schema change needed.
- **Bio-scrape verification now.** Deferred to UF5 as an explicit OAuth-vs-bio-code
  design decision; the sensitive-site gate it unlocks is already built and tested.
