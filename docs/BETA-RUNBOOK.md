# Ayin private-beta runbook (M5)

The beta exists to answer one question with real users: *does the §13.7
thesis hold?* This runbook is the operational half of that measurement —
the code half is `python -m ayin.beta.gonogo`.

## Ground rules (non-negotiable — CLAUDE.md)

- **Self/consented subjects only.** Every participant scans themselves.
  Recruiting copy must say so explicitly; anyone asking to "check someone"
  is declined and pointed at `/exclude` for the other person's rights.
- The safety floor is live for the whole beta: audit, rate limits, abuse
  gates, exclude-me, delete-everything. None of it is feature-flagged off.
- Beta data is real subject data. At beta end, email every participant a
  delete-everything reminder; offer one-click account deletion.

## Pre-flight (before wave 1)

1. Real connector keys in the deployment env (`BREACH_API_KEY`,
   `SEARCH_API_KEY`) — and **counsel sign-off recorded** for each source,
   flipping `counsel_signoff=True` in its governance block (PRD §11.4).
   Until then production enablement is refused by the registry, by design.
2. Broker registry: verify probe URLs/markers for an initial 10-broker
   subset against live sites; set `probe.enabled: true` only for verified
   entries (`verify_before_enable` is per-entry).
3. `BETA_INVITE_REQUIRED=true`, `APP_ENV=production`, real `APP_SECRET`,
   `VAULT_MASTER_KEY` (KMS), `COOKIE_SECURE=true` — the app refuses to boot
   in production with dev placeholders (config.assert_production_safe).
4. Generate wave-1 invites:
   `python -m ayin.beta.invites create --count 25 --max-uses 1 --note wave-1`

## Recruiting & consent

Target cohort (PRD §6.1 personas): privacy-anxious professionals,
post-breach responders, online-visible people (creators, journalists),
dating-safety users scanning **themselves**. 25–50 users across 2 waves.

Consent language (include in the invite email): "Ayin will scan publicly
available sources for identifiers you verify you control, store the
findings and a score under encryption, and let you delete everything at
any time. Every access to your data is audited."

## Weekly cadence

| When | What | How |
|---|---|---|
| Mon | Funnel review | `python -m ayin.analytics.report --days 7` — log numbers in the beta journal |
| Wed | Accuracy QA | `python -m ayin.qa.sample --n 50` → manual review (qa/README.md) → `python -m ayin.qa.report` |
| Daily | T&S queue | review open `AbuseSignal` rows (holds, appeals — 48h SLA on appeals); audit-chain spot check `verify_chain` |
| Fri | Interviews | 2–3 sessions from that week's activated users (guide below) |

## Interview guide (~25 min; the §13.7 qualitative gate)

1. **The aha:** "Walk me through your report. Did you learn something you
   didn't know was out there?" (majority must say yes — hard gate)
2. **Comprehension:** "In your own words, what does your score mean?"
   (listen for *exposure of data*; if they say "my trustworthiness," our
   FCRA-line copy is failing — fix immediately)
3. **Action:** "You did / didn't start a fix — what made it easy/hard?"
4. **Trust:** "Anything in the report you doubted?" (feed doubts into the
   QA sample)
5. **Pull:** "Would you pay for Ayin to watch this and remove listings for
   you? What would that be worth monthly?" (calibrates §16 pricing)

Log each interview against the participant's pseudonymous `user_ref`,
never alongside their findings.

## Go/no-go (end of week 12)

```bash
python -m ayin.beta.gonogo --days 90 --qa-reviewed qa/latest-reviewed.jsonl
```

GO → Phase 1 (monitoring + automated removal engine). INSUFFICIENT DATA →
extend the beta, don't lower the bar. NO-GO / kill criteria tripped →
PRD §13.7: rethink the wedge before building the paid engine; the decision
meeting reviews interviews alongside the scorecard.

## Incidents

- **Source misbehaving / ToS change:** disable centrally
  (`registry.disable(connector_id)`); findings from it stay flagged by
  source attribution.
- **Suspected key/PII exposure:** rotate `APP_SECRET`/keys; for affected
  subjects run vault shred + notify; the audit chain is the forensic spine.
- **Abuse incident:** safety hold the account (block-severity
  `AbuseSignal`), preserve audit records, escalate per AUP.
