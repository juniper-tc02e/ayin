# Consent T1 — enablement backlog (outstanding before `consent_t1_enabled` can flip on)

**Status (2026-07-11):** the consent-gated third-party scan feature (T1) is merged to `main`,
**flag OFF in prod**, not deployed. Three adversarial audit cycles were run; all *clean-fix*
findings (1 critical + all highs that were patchable + most mediums) are committed. This doc is
the **remaining work** — a deliberate design pass, not more patching — that must land + re-pass a
clean audit before the flag is turned on. Nothing here is live; there is no urgency.

See [`ADR-0007`](adr/0007-consent-gated-third-party-scans.md) (feature + audit remediation log) and
[`ADR-0008`](adr/0008-t1-data-model-tier-and-identifier-scope.md) (tier + identifier-scope data model).

## 1. HIGH — identifier scope: a join table (the design item)

**Problem.** `Identifier.consent_requester_id` (a single nullable column, migration 0020) can't
express "this identifier is scoped to requester A **and** B." Consequences the audit confirmed:
- A subject's **verified email** anchor is shared (NULL-tagged), so a third-party scan currently
  allows *any* verified email of the subject, not just the one that requester was consented for
  (a real account with several verified emails leaks them all).
- A handle both requesters confirm is tagged to whoever seeded it first → the other requester
  under-scans (benign) — but the shared-scope case has no clean representation.

**Design.** Replace the column with a many-to-many **scope join table**:

```
consent_identifier_scope(identifier_id FK→identifiers ON DELETE CASCADE,
                         requester_user_id FK→users  ON DELETE CASCADE,
                         PRIMARY KEY (identifier_id, requester_user_id))
```

- `accept_consent` inserts one `(identifier_id, requester_user_id)` row per handle **and** for the
  verified email anchor it authorized — so the email is scoped per-requester, not shared.
- `eligible_seed_identifiers(subject_id, requester_user_id)` for a third-party scan = identifiers
  with a scope row for THIS requester (join), full stop — no broad "any verified email" clause.
  Self-scan (owner == requester) = identifiers with NO scope rows (the subject's own). T0 path
  unchanged.
- Deleting a requester drops their scope rows (not the identifier) — fixes item 4 below.
- Migration: add the table, backfill from `consent_requester_id`, then drop the column.

## 2. MEDIUM — `GET /consent/grants` discloses subject email un-audited
`my_grants` returns `subject_email` for each grant with **no `record_data_access`** row, unlike
every other subject-data route. Add the audit write (it's the requester's own grant, so the
disclosure is fine — the missing bit is the audit spine).

## 3. MEDIUM — revoke-link token bound by time, not grant identity
`revoke_by_token` bounds the token to the grant's expiry, but a stale/leaked link can still revoke
a *different, later* grant for the same (subject, requester) pair. Bind the revoke action to the
specific grant the token was minted for (revoke that grant + its concurrent siblings, not a future
unrelated one). Only ever reduces access, so low severity.

## 4. MEDIUM — `consent_requester_id` FK `ON DELETE CASCADE`
A requester deleting their account cascade-deletes the consent-scoped `Identifier` rows — which live
on the *subject's* record. Subsumed by item 1 (the join table's scope rows cascade, the identifier
survives). Until then, consider `ON DELETE SET NULL` — but note NULL = "subject's own", which would
then be self-scan-eligible, so the join table is the real fix.

## 5. MEDIUM — uvicorn trusts `X-Forwarded-For` from any internal peer
`--forwarded-allow-ips='*'` trusts XFF from any container on the docker network, not just Caddy.
Caddy now overwrites XFF (Caddyfile `header_up`), so the external path is closed, but scope
`--forwarded-allow-ips` to Caddy's address/CIDR (or move the throttle to a shared **Redis** limiter,
which also fixes the per-worker in-memory split) for defense in depth.

## 6. Already-documented lower residuals (ADR-0007)
Connector scope-limiting for `scope="footprint"`; login-less subject can't later claim its email for
a real account; per-target harassment cap is per-account (prod mitigates via invite-only signup);
no per-handle confirmation on accept; `POST /scans` has no route-layer relationship check (the gate
enforces).

## Definition of done for enablement
All of §1–§5 land with tests; a fresh adversarial audit (the `consent-reaudit` workflow) returns
**no confirmed high/critical**; then flip `consent_t1_enabled` on in a deploy — behind the existing
flag, with the always-on gate unchanged.
