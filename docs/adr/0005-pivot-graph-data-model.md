# ADR 0005 — Pivot-graph data model: sourced candidate links for the agentic self-scan

- **Status:** Proposed
- **Date:** 2026-06-13
- **Context:** Phase 2 ("SuperAyin", [`BUILD-PLAN.md`](../BUILD-PLAN.md) §S2)
  extends the B2 planner ([`ADR-0003`](0003-qwen-llm-integration.md)) across a
  fleet of sourced public-records connectors and must walk a **pivot graph** — a
  finding on one source yields a new *sourced* fact (a username → an email → a
  city) that seeds the next source, so the scan reaches the long tail of a
  person's *own* exposure. The MVP's flat `Finding` rows (keyed `scan_id` +
  `dedupe_key`, fanned out from verified seeds only) cannot represent
  cross-source linkage or multi-hop derivation. The model for it must make three
  failures *structurally* impossible: inventing a fact (CLAUDE.md #5), merging a
  namesake (FR-ER-1 — "false-merge is the enemy"), and drifting into third-party
  scanning (CLAUDE.md #1).

## Decision

**Reuse the existing candidate lifecycle; add one new edge entity.** Do **not**
introduce a separate Candidate table. `Finding.match_status` already models the
lifecycle — `POSSIBLE` = unconfirmed candidate, `AUTO_MATCHED`/`CONFIRMED` =
finding, `REJECTED` = killed — and the scorer already counts only
`AUTO_MATCHED`/`CONFIRMED`. A pivot-derived weak match is simply a `Finding` born
`POSSIBLE`. The only net-new concept is the **edge** that produced it.

**`PivotLink` is a typed, sourced edge.** Fields: `id`, `scan_id`, `subject_id`,
`from_finding_id`, `from_identifier_id` (nullable), `derived_identifier_kind`,
`derived_value_normalized`, `derived_value_vault_ref` (sensitive values go to the
vault, never operational tables), `source` (the connector that *asserted* the
link), `source_url`, `captured_at`, `confidence` [0–1], `hop_depth`, `status`
(`PROPOSED → MATERIALIZED → CONFIRMED | REJECTED`). **Every edge is sourced.**
The LLM may *propose traversing* an edge; it may never author an edge's content —
the same line the citation guard already enforces for narrative claims.

**`correlation_group_id` on `Finding`** clusters findings the resolver believes
describe the same exposure across sources, giving corroboration ("3 independent
sources confirm this") and cross-source confidence aggregation a home. Grouping
is rules + threshold; LLM assist is gray-zone-only and never load-bearing
(mirrors B4).

**Materialization rule (the safety crux).** A `PivotLink` becomes a new seed only
when **(a)** its source confidence clears the seed-promotion threshold **and**
**(b)** the resolver attaches it to the verified subject above the auto-match
threshold *or* the user confirms it. Below threshold it stays a candidate edge —
surfaced for review, never auto-traversed into deeper hops. The MVP's
unverifiable-seed cap (0.65) carries over, so a namesake can never silently seed
a pivot chain.

**Bounded traversal.** A `hop_depth` cap (config, default 3), a per-scan pivot
budget (max derived seeds), and a cycle guard bound the walk. The planner
proposes the next pivot among *materialized* edges only; the caps and budgets are
code, not model decisions.

**Subject-scoped by construction.** Every `PivotLink` carries the scan's
`subject_id`; derived identifiers are candidate facts *about the verified self*,
gated by the same verification + visibility rules as seeds. Nothing here creates
a `Subject` or scans an identifier the requester hasn't anchored. The
`Scan` DB CHECK (`tier = t0`, `purpose = self`) is untouched.

## Consequences

- **Additive migration only:** new `pivot_links` table + `correlation_group_id`
  column on `findings` + new enum values. `Finding`/`Score` semantics are
  unchanged; the scorer still counts only `AUTO_MATCHED`/`CONFIRMED`, so a
  candidate edge can never move the number on its own.
- **The candidate gate is the human-in-the-loop checkpoint.** Pivots can be
  aggressive — chase weak links — *precisely because* nothing they surface
  scores or re-seeds without crossing a threshold or a user confirm.
- **New audit events** (`scan.pivot_proposed`, `scan.pivot_materialized`,
  `scan.candidate_generated`), each with source + confidence + reasoning, extend
  the E1 activity-trail allowlist.
- **The false-merge surface grows** with multi-hop chains. The M4-3
  findings-accuracy / false-merge harness must gain multi-hop pivot cases and
  hold the ≥ 90% precision floor **before** the S5 connector fleet expands — this
  is the gating risk for the phase.
- **Retention:** derived sensitive values live in the vault (`vault_ref`), purge
  on the retention timer, and crypto-shred on subject delete; the `PivotLink` row
  persists as provenance (edge + source + confidence), but the sensitive value
  does not sit in operational tables.
- **Opens nothing for third-party scanning:** the model is subject-scoped, so
  T1–T3 stay blocked by the DB constraint and remain a separate ADR.

## Revisit triggers

Multi-hop false-merge rate failing the ≥ 90% precision floor in QA · any pressure
to let the LLM author edge *content* (must not — violates #5) · pivot
budgets/latency turning scans unbounded · a derived-identifier path that would
scan an un-anchored identifier (must not — violates #1) · graph scale demanding a
real graph store over Postgres edges/JSONB.
