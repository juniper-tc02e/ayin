# Username Footprint connector — design plan + build prompts

**Status:** plan (Phase 2 / "SuperAyin"). Not on the MVP critical path; keep off the
frozen submission `main` until after judging — land on `superayin-phase2`.

**One-line:** port Sherlock's site-presence engine into Ayin as a **self-scan
`username_footprint` connector** — same capability (is this handle present on N
sites?), Ayin's discipline (governance, robots/UA, consent, ER, scoring, audit,
vault, exclude-me). It is the sibling of the existing `broker_detect` connector.

---

## 0. The non-negotiable reframe (read first)

Sherlock's headline feature — *"give me any username and I'll find it everywhere"* —
is **third-party enumeration of an arbitrary person**. That directly violates Ayin
constraint #1 (self-scan only) and fails the §20.5 decision rule (more useful to a
stalker than to a self-protector). So we **do not** port that. We port the *engine*
and apply it to the **requester's own asserted/owned usernames**, inside the existing
safety floor. Net effect: a user learns "here is everywhere my handle appears
publicly," scored and with removal steps — strictly *better* than Sherlock for the
defensive use case, and legal/judge-safe.

**Take from Sherlock:** the detection manifest (`data.json` shape), the three
detection methods (`status_code` / `message` / `response_url`), `regexCheck`,
per-site request shaping (method/payload/headers), and the 400-site knowledge base
(as *input* to a vetting pipeline, not a wholesale import).

**Leave behind:** arbitrary targets, Tor / `--unique-tor` / proxy rotation (block
evasion → conflicts with ToS-respect and reads as detection-evasion), aggressive
fan-out, and any NSFW probing that isn't explicitly opted into and ownership-verified.

---

## 1. Ayin vs Sherlock

| | Sherlock | Ayin `username_footprint` |
|---|---|---|
| Target | **anyone's** username (CLI arg) | **requester's own** asserted/verified handles only |
| Consent model | none | verified requester + asserted/owned seeds + exclude-me |
| Output | flat list of URLs to stdout/CSV | `NormalizedFinding`s: source + captured_at + confidence + sensitivity |
| Truth handling | "claimed / available" | claimed / available / **unknown** (honest; no false "found") |
| After the hit | nothing | entity resolution (confirm/reject), exposure score, ✦ Qwen remediation |
| Network ethics | Tor/proxy to dodge blocks | identifying UA, robots respected, paced, no evasion |
| Site set | all 400+, unvetted | vetted allowlist; each row carries governance + ToS status |
| Sensitive data | dumped to disk | `sensitive_payload` → PII vault; crypto-shred on delete |
| Accountability | none | hash-chained audit on every probe + every read |
| License | MIT | AGPL-3.0 (MIT-compatible; attribute the derived manifest) |

We keep Sherlock's reach; we add the consent model, the scoring/remediation that makes
it *actionable*, and the accountability that makes it *defensible*.

---

## 2. Where it slots in (architecture)

```
INPUT → DISCOVERY → RESOLUTION → ENRICHMENT → SCORING → REPORT → REMEDIATION
                 └── username_footprint connector lives in DISCOVERY,
                     same contract as breach/search/broker (M1-2..4)
```

- **New connector** `backend/ayin/connectors/username/` — `connector.py`,
  `detection.py`, `sites_loader.py`, `sites.yaml`, plus a one-off
  `tools/sherlock_import.py` converter. Model it on
  `backend/ayin/connectors/broker/` (detector + registry_loader + registry.yaml).
- **`supported_kinds = frozenset({IdentifierKind.USERNAME})`.**
- Emits `NormalizedFinding(category=SOCIAL, …)` → flows into the existing
  RESOLUTION (M2 ER + B4 Qwen assist), SCORING (versioned rubric), REPORT (B1
  grounded narrative), REMEDIATION (B3 personalized steps). **No core changes** —
  the connector contract is the seam.

---

## 3. Site manifest (`sites.yaml`) — the data model

A **vetted, Ayin-owned** YAML (not raw Sherlock JSON). One row per site:

```yaml
- id: github
  name: GitHub
  category: code              # code | social | forum | gaming | creative | dating | adult | other
  url_template: "https://github.com/{username}"
  url_main: "https://github.com/"
  url_probe: null             # optional alternate endpoint (Sherlock urlProbe)
  detection:
    method: status_code       # status_code | message | response_url  (Sherlock errorType)
    found_codes: [200]        # status_code: codes that mean "present"
    notfound_markers: []      # message: substrings that mean "absent" (Sherlock errorMsg)
    notfound_url_contains: "" # response_url: substring of the not-found redirect (errorUrl)
  regex_check: null           # username must match (Sherlock regexCheck) else skip site
  request:
    method: GET               # GET | HEAD | POST | PUT
    payload: null             # POST/PUT body (Sherlock request_payload)
    headers: {}               # extra headers (Sherlock headers)
  sensitivity: low            # low | medium | high | critical (drives score + vault)
  nsfw: false                 # adult site → opt-in + ownership-verified only
  removable: true
  opt_out:
    url: "https://github.com/settings/admin"
    instructions: "Settings → Account → Delete account, or set the profile private."
    expected_processing: "immediate"
  governance:
    access_method: public_page
    tos_status: ok            # unvetted | ok | blocked | auth_required  ← only `ok` probes in prod
    robots_required: true
    rate_limit_per_minute: 30
  fixtures:                   # contract tests only — clearly-fake / well-known-public handles
    claimed: "torvalds"
    unclaimed: "ayin-nope-zzq-000"
```

**Detection-method mapping (Sherlock → Ayin):**

| Sherlock `errorType` | Ayin `detection.method` | "present" when … |
|---|---|---|
| `status_code` (+`errorCode`) | `status_code` | response status ∈ `found_codes` |
| `message` (+`errorMsg`) | `message` | 200 **and** none of `notfound_markers` in body |
| `response_url` (+`errorUrl`) | `response_url` | final URL does **not** contain `notfound_url_contains` |

**Honesty rule (the key upgrade over Sherlock):** if the site's contract looks
changed (unexpected status, marker neither clearly found nor not-found), classify
**`unknown`** → emit *nothing* (or a low-confidence "needs review"), never a false
"found." Sherlock's binary claimed/available is a known false-positive source; Ayin
refuses to assert.

---

## 4. ToS / governance vetting pipeline

Sherlock's 400 sites are **input**, not output. Each starts `tos_status: unvetted`
and **never probes** until reviewed:

1. `tools/sherlock_import.py` ingests Sherlock's `data.json`, emits proposed
   `sites.yaml` rows with `tos_status: unvetted`, dedupes, drops anything requiring
   auth, and tags `nsfw`/`tags: [adult, gaming]`.
2. Human/counsel review per row → `ok` (public profile-existence check is
   ToS-compatible + robots-allowed), `blocked` (ToS forbids automated access), or
   `auth_required` (skip — behind a login).
3. The connector only ever probes `tos_status: ok` rows; `blocked`/`auth_required`/
   `unvetted` are skipped, logged, and never hit the network.
4. Ship a **seed allowlist of ~15–25 clearly-OK sites** (GitHub, Reddit, public
   Instagram/X profile pages where compliant, Medium, Steam, etc.); grow it behind
   review. `counsel_signoff` on the connector's `SourceGovernance` gates prod
   enablement (same as `broker_detect`).

Attribution: the derived manifest is based on Sherlock (MIT) — keep an MIT notice +
provenance comment in `sites.yaml` and the importer; record the derivation in an ADR.

---

## 5. Detection engine (`detection.py`) — the port

Pure, transport-injectable, no I/O policy of its own (the connector owns
robots/pacing/rate-limit):

```
classify(site, username, http) -> "present" | "absent" | "unknown"
  if site.regex_check and not re.fullmatch(site.regex_check, username): return "absent"  # site can't hold it
  url = site.url_probe or site.url_template.format(username=quote(username))
  resp = http.request(site.request.method, url, headers=..., data=site.request.payload, timeout, follow_redirects)
  match site.detection.method:
    status_code:   return present if resp.status in found_codes else absent (or unknown on 5xx/unexpected)
    message:       if resp.status != 200: return unknown
                   body = resp.text.lower()
                   return absent if any(m.lower() in body for m in notfound_markers) else present
    response_url:  return absent if notfound_url_contains in str(resp.url) else present
```

- **Concurrency:** bounded + respectful — token bucket (contract) + a small pool
  (≤5) with per-host pacing. **Not** Sherlock's wide thread fan-out.
- **Per-site isolation:** one broken/timeout site is recorded + skipped, never fails
  the scan (exactly like `broker_detect.fetch`).
- **Reuse from `broker/detector.py`:** the `_may_probe` robots.txt cache, the
  identifying `USER_AGENT`, `PROBE_PACING_SECONDS`, and the try/skip-on-`TransportError`
  loop. Lift these almost verbatim.

---

## 6. Username ownership & consent (the heart)

A username can't be email-verified, so model **ownership tiers**:

- **Tier 0 — asserted** (default): user typed it. The *scan* still requires a
  verified anchor (the email, FR-AUTH-1) to run at all; the username is an additional
  owned seed. Footprint findings are emitted as **`match_status: possible`** →
  surfaced for ER confirm/reject. Non-sensitive categories only.
- **Tier 1 — verified** (optional upgrade): prove control via a one-time code in the
  profile bio/display-name, or platform OAuth where available. Verified ownership
  raises confidence and **unlocks sensitive categories** (e.g. dating/`nsfw` sites,
  behind explicit opt-in).
- **exclude-me (hard gate):** a global hashed "exclude this username" list is checked
  **before any probe**. A handle on it is never checked — even under an ownership
  claim — which blocks "claim someone else's handle to scan them." This is the
  safety-floor "Exclude me from Ayin" applied per-identifier.

This is what keeps the feature on the *self-protection* side of §20.5: verified
requester + owned seeds + per-handle exclusion + audit + rate limits.

---

## 7. Entity-resolution hook

- Each present-handle is a **candidate identity**, not a fact about the person.
  Route through the existing M2 ER rules + B4 Qwen second-opinion (advice-only,
  never moves `match_status`).
- **Cross-site corroboration** raises confidence: same handle + matching display
  name / avatar hash / bio across ≥2 sites ⇒ stronger "this is one identity."
- **False-merge is the enemy (FR-ER-1):** keep thresholds conservative; a bare
  handle match stays `possible` until the user confirms or corroboration is strong.
  Never auto-merge two people who share a handle.

---

## 8. Scoring hook

- Add a versioned **`username_footprint` subscore**: each *confirmed* presence
  contributes by `site.sensitivity` (dating/adult ≫ code), corroboration count, and
  **linkage** (one handle tying multiple identities together is itself an exposure —
  it's how a stranger pivots from your GitHub to your everything).
- Strictly **exposure/exploitability of data**, never a judgment of the person
  (FCRA bright line). Bump the rubric version; add rubric tests.

---

## 9. Remediation hook

- Per-site removal/hardening steps (delete account · set private · unlink · scrub
  bio), attached like the broker `opt_out` block. B3 Qwen personalizes the steps and
  orders them by score-delta. Where a site has a known deletion flow, link it.

---

## 10. Safety gates (floor stays on — never a toggle)

- **Volume/rate:** sites-per-scan cap, usernames-per-scan cap, scans-per-day
  (existing `rate_limit_*`); per-site token bucket from `SourceGovernance`.
- **Abuse heuristics:** many *distinct* usernames in a short window, or usernames
  with no plausible link to the verified account → refuse + `AbuseSignal`.
- **Audit:** hash-chained `AuditRecord` on every probe and every finding read
  (staff included).
- **No minors:** if signals indicate the subject is a minor, refuse (constraint #3).
- **Retention/vault:** sensitive payloads (avatar, bio, NSFW presence) →
  `sensitive_payload` → PII vault; crypto-shred on delete; short retention.
- **exclude-me** enforced pre-probe (§6).

---

## 11. Tests / QA (definition of done)

- **Detection unit tests:** for each method (`status_code`/`message`/`response_url`),
  a mock transport asserts present/absent/**unknown**, using each site's
  `fixtures.claimed`/`unclaimed`.
- **Contract tests:** governance present, `source==id`, attribution complete,
  `regex_check` gating, robots-disallow skip, exclude-me skip, per-site isolation,
  ownership-tier → confidence.
- **ER threshold tests:** no false merge on shared handles; corroboration raises
  confidence as specified.
- **Scoring tests:** rubric version bump; sensitivity/linkage weighting.
- **QA harness:** maintain ≥90% precision on *shown* findings (PRD §13.7) — i.e.
  honest `unknown` handling beats false "found."
- **Fixtures use clearly-fake or well-known-public handles only**; never real PII.

---

## 12. Phased tasks

| Task | Deliverable |
|---|---|
| **UF1** | `sites.yaml` schema + `sites_loader.py` + 15–25-site vetted seed + `tools/sherlock_import.py` (proposes `unvetted` rows from Sherlock data.json) |
| **UF2** | `detection.py` — 3 methods + regex + request shaping, transport-injected, full unit tests |
| **UF3** | `username/connector.py` — `Connector` subclass (governance, robots/UA/pacing/isolation, exclude-me, ownership-tier confidence) + contract tests; register it |
| **UF4** | ER + scoring + remediation wiring (corroboration, `username_footprint` subscore, per-site removal steps) |
| **UF5** | optional Tier-1 username verification (bio-code) + sensitive-category gating |
| **UF6** | frontend "Username footprint" panel (by-site results, confirm/reject, remove links) |
| **UF7** | safety/abuse/audit hardening + QA precision harness + ADR (Sherlock derivation, MIT attribution) |

---

## 13. Build prompts (self-contained — refer to these when building)

> Each prompt is runnable as-is (by me or a subagent). They assume the connector
> contract in `backend/ayin/connectors/base.py` and the **template**
> `backend/ayin/connectors/broker/` (detector + registry_loader + registry.yaml).
> Global constraints for **every** prompt: self-scan only; complete `SourceGovernance`
> with `counsel_signoff=False` until reviewed; emit fully-attributed
> `NormalizedFinding`s; honest `unknown`; exclude-me checked pre-probe; no minors;
> fixtures are clearly-fake/public handles; write an audit record on subject-data
> access; keep changes surgical; this lands on `superayin-phase2`, not `main`.

### Prompt UF1 — site manifest + loader + Sherlock importer
```
Build the Username Footprint site manifest layer, modeled on
backend/ayin/connectors/broker/ (registry.yaml + registry_loader.py).
1. Create backend/ayin/connectors/username/sites.yaml with the row schema in
   docs/plans/username-footprint-connector.md §3. Seed 15–25 sites whose public
   profile-existence check is ToS-compatible and robots-allowed (start: GitHub,
   Reddit, Medium, Steam, GitLab, Keybase, Replit, Telegram t.me, Pastebin,
   Wikipedia, HackerNews, Mastodon-instance, About.me, Patreon-public, Vimeo).
   Each row: tos_status: ok, correct detection.method + params, regex_check where
   the platform restricts charset, sensitivity, removable + opt_out, fixtures
   (claimed = a well-known PUBLIC handle or synthetic; unclaimed = an obviously
   fake handle). NSFW/dating sites: do NOT seed here.
2. Create sites_loader.py: pydantic models (Site, Detection, Request, OptOut,
   Governance, Fixtures) + load_sites(path) with validation; reject rows missing
   detection params for their method; expose only tos_status=="ok" via an
   enabled_sites() helper.
3. Create backend/tools/sherlock_import.py: read a Sherlock data.json (path arg),
   map errorType→detection.method (status_code/message/response_url), carry
   regexCheck/request_method/request_payload/headers/isNSFW/tags, set
   tos_status: unvetted, drop auth_required-looking entries, and PRINT proposed
   YAML rows to stdout (never auto-merge into sites.yaml). Add MIT attribution +
   provenance header.
Tests: sites_loader validation (good + each bad-row case); importer maps a small
fixture data.json to the expected rows. Done when load_sites parses the seed file
and enabled_sites() returns only ok rows.
```

### Prompt UF2 — detection engine
```
Implement backend/ayin/connectors/username/detection.py per §5.
classify(site: Site, username: str, client: httpx.Client) -> Literal["present",
"absent","unknown"]. Implement all three methods exactly as the mapping table in
§3 specifies, regex_check gating first, request shaping from site.request, and the
HONEST unknown rule (unexpected status / ambiguous markers → "unknown", never a
false present). Pure function over an injected httpx client/transport — no robots,
no sleeps, no rate-limit here (the connector owns those).
Tests (backend/tests/connectors/test_username_detection.py): a MockTransport per
case asserting present/absent/unknown for status_code, message, response_url; a
regex_check rejection; a 5xx→unknown; a redirect-to-login→absent for response_url.
Use each seed site's fixtures.claimed/unclaimed where practical. Done when every
method has present+absent+unknown coverage and tests are green.
```

### Prompt UF3 — the connector
```
Implement backend/ayin/connectors/username/connector.py as a Connector subclass
(backend/ayin/connectors/base.py), modeled closely on
backend/ayin/connectors/broker/detector.py.
- id="username_footprint", supported_kinds=frozenset({IdentifierKind.USERNAME}).
- Complete SourceGovernance: access_method=PUBLIC_PAGE, legal_basis describing
  self-scan handle-presence on the requester's OWN asserted/verified usernames,
  tos_ref pointing at sites.yaml per-row tos_status, data_classes
  ["handle-presence","profile-url"], counsel_signoff=False, sensible rate limit.
- fetch(): load enabled_sites(); for each, (a) skip if username on the exclude-me
  list [inject an ExcludeList checker], (b) robots check via the broker detector's
  _may_probe pattern, (c) classify() via detection.py, (d) on "present" append a
  RawResult{site_id, profile_url}. Pace with self._sleep; isolate per-site errors;
  bounded concurrency optional (token bucket stays authoritative).
- normalize(): map each present hit to NormalizedFinding(category=SOCIAL,
  sensitivity from site, source_url=profile_url, confidence by OWNERSHIP TIER
  (asserted→~0.5 / verified→~0.8) blended with detection strength, summary
  "Your handle '<u>' has a public profile on <site>", payload {site, category,
  removable, opt_out_*, ownership_tier, namesake_risk: tier==asserted},
  sensitive_payload (bio/avatar) → vault, dedupe_key
  f"username_footprint:{site_id}:{username}").
Register via @registry.register and add to bootstrap (gated like the others).
Tests: contract test (governance, source==id, attribution, exclude-me skip, robots
skip, ownership-tier confidence, per-site isolation) with a fake sites.yaml +
MockTransport. Done when a self-scan over the fixtures yields correctly-attributed
SOCIAL findings and the exclude-me + robots gates are proven.
```

### Prompt UF4 — ER + scoring + remediation wiring
```
Wire username_footprint findings into RESOLUTION, SCORING, REMEDIATION.
- ER: present-handles enter as match_status=possible; add cross-site corroboration
  (same handle + matching display_name/avatar_hash across ≥2 sites raises
  confidence) into the existing M2 ER; keep B4 Qwen advice-only. Add false-merge
  tests (two people, same handle → never merged).
- Scoring: add a versioned `username_footprint` subscore to the rubric — weight by
  site.sensitivity, corroboration count, and a linkage term (handle tying multiple
  identities). Bump rubric version; add rubric unit tests. Exposure only, never a
  judgment of the person (FCRA).
- Remediation: emit per-site removal/hardening steps from site.opt_out; let B3 Qwen
  personalize + order by score-delta.
Done when a confirmed handle moves the score via the new subscore and the report
narrative (B1) can cite these findings with sources.
```

### Prompt UF5 — Tier-1 username verification (optional)
```
Add optional username ownership verification to upgrade asserted→verified.
- Flow: issue a one-time code; user places it in their profile bio/display-name;
  Ayin re-fetches the public profile and confirms the code (or platform OAuth where
  supported). On success mark the Identifier verified and unlock sensitive
  categories (nsfw sites) behind an explicit per-scan opt-in.
- Gate: sensitive/nsfw sites in sites.yaml only probe when the username is Tier-1
  verified AND the user opted in for this scan. Audit the verification.
Tests: verification success/failure; sensitive sites skipped for Tier-0; unlocked
for Tier-1+opt-in. Done when ownership tier provably gates sensitive probing.
```

### Prompt UF6 — frontend "Username footprint" panel
```
Add a FootprintPanel to the report/dashboard (model on FindingsList.tsx +
HardeningChecklist.tsx). Group username_footprint findings by site/category; each
row: site, "present" badge, confidence, confirm/reject (ER), and a removal-steps
expander (✦ Qwen personalized where present). Show the ownership tier and a
"verify this handle" CTA for Tier-0. Render all source/connector-derived strings as
strict text (untrusted). Verify live in the browser. Done when a self-scan shows the
handle footprint with working confirm/reject + remove links.
```

### Prompt UF7 — safety, abuse, audit, QA, ADR
```
Harden + document.
- Safety: enforce sites-per-scan + usernames-per-scan caps; abuse heuristic (many
  distinct usernames fast, or usernames unlinked to the verified account → refuse +
  AbuseSignal); confirm exclude-me is checked pre-probe; refuse on minor signals.
- Audit: hash-chained AuditRecord on every probe and every footprint-finding read.
- Vault/retention: sensitive_payload → PII vault; crypto-shred on delete.
- QA: extend the findings-accuracy harness to assert ≥90% precision on shown
  username findings (honest unknown handling).
- ADR docs/adr/00NN-username-footprint.md: the self-scan reframe, Sherlock (MIT)
  derivation + attribution, ToS-vetting pipeline, ownership tiers, exclude-me.
Done when abuse + exclude-me + audit are test-proven and the ADR is committed.
```

---

## 14. What we deliberately do NOT build (and why)

- **Arbitrary-target enumeration** — violates self-scan (#1) + §20.5; it's the
  stalkerware shape.
- **Tor / `--unique-tor` / proxy rotation** — block-evasion; conflicts with
  ToS-respect (#3) and reads as detection-evasion.
- **Wholesale 400-site import** — each site needs ToS + robots vetting first;
  unvetted sites never probe.
- **NSFW probing without ownership verification + opt-in** — sensitive; gated behind
  Tier-1 (§6) and never for minors.
- **Storing raw cross-site dossiers** — minimize what we keep (#6); findings + score
  only, sensitive bits in the vault.

These exclusions are *why* the feature is shippable: it keeps Ayin a privacy tool.
