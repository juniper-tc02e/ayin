# Ayin — Product Requirements Document & SaaS Plan

> **Ayin** (Hebrew *ʿayin*, "eye" / "to see") — an open-source-intelligence scanner that shows a person exactly what the internet already knows about them, scores the risk, and helps them shrink it.

| Field | Value |
|---|---|
| Document | Product Requirements Document + SaaS Business Plan + MVP Spec |
| Version | 0.1 (Draft for review) |
| Status | Proposed |
| Author | Founding team |
| Date | June 9, 2026 |
| Scope | One aligned document covering vision → product → architecture → MVP → GTM → economics → compliance |
| Audience | Founders, eng/design leads, prospective investors, early advisors |

---

## How to read this document

This is a single source of truth deliberately written so three layers stay aligned:

1. **The Product PRD** (Sections 5–12) — what we are building and why, in enough detail to design and scope.
2. **The MVP** (Section 13) — the narrow, buildable first cut, drawn directly from the PRD so nothing in the MVP contradicts the long-term product.
3. **The SaaS plan** (Sections 14–22) — how it becomes a business: roadmap, pricing, unit economics, GTM, metrics, and the legal/safety architecture that makes the whole thing viable.

Every pricing tier maps to a roadmap phase; every roadmap phase maps to product modules; every module maps to data sources and safeguards. Where a decision is still open, it is flagged in **Section 22: Open Questions**.

A note on framing, because it governs everything else: Ayin is built on **"open OSINT with safeguards."** It can scan any name from publicly available sources, but every scan is gated by identity verification, purpose attestation, rate limits, audit logging, and a hard prohibited-use policy. The defensive, consent-forward use case (*"show me what's exposed about me, then help me remove it"*) is the wedge and the brand. The safeguards are not a compliance afterthought bolted on at the end — they are the product's core architecture and its primary moat. See **Section 7**.

---

## Table of contents

1. Executive summary
2. Problem & opportunity
3. Vision, mission & principles
4. Goals & non-goals
5. Market & competitive landscape
6. Users & personas
7. The scan model & trust architecture (core)
8. Product overview & capabilities
9. Functional requirements (feature specs)
10. System architecture
11. Data sources & acquisition strategy
12. UX & key flows
13. The MVP (in depth)
14. Roadmap
15. Go-to-market
16. Pricing & packaging
17. Business model & unit economics
18. Metrics & KPIs
19. Legal, compliance & risk
20. Trust, safety & ethics charter
21. Team & org to build it
22. Open questions, assumptions & decisions
23. Appendices

---

## 1. Executive summary

**What it is.** Ayin is a SaaS that performs an OSINT scan of a person from publicly available sources — breached credentials, data-broker listings, social and public-web footprint, public records, and exposed images — then resolves it into one identity profile, scores the exposure, and drives remediation (removal requests, hardening steps, ongoing monitoring).

**Why now.** Three forces converge in 2026. (1) Exposure is exploding: breach corpora exceed 12 billion records across 900+ breached sites, and AI makes that data trivially exploitable for phishing, impersonation, and account takeover. (2) Regulation is creating both demand and rails: California's Delete Act and its DROP deletion platform went live January 1, 2026, normalizing the idea that individuals can and should reclaim their data. (3) The two adjacent markets are large and growing fast — personal data-removal services were ~$1.68B in 2024 heading to ~$7.99B by 2033 (18.2% CAGR), and the broader OSINT market is ~$15.9B in 2026 heading to ~$133.6B by 2035 (26.7% CAGR).

**The wedge → expansion.** Start B2C with a free "see your exposure" self-scan that converts to paid monitoring + removal (the DeleteMe/Optery/Incogni demand, but with a richer scan and a more honest report). Then expand the *same engine* into B2B: executive-protection and employee-exposure monitoring for security teams, plus a vetted API. One scanning core, two go-to-market motions.

**Differentiation.** Existing players are split: data-removal services (DeleteMe, Optery, Incogni) only address data brokers; breach checkers (Have I Been Pwned) only address breaches; pro OSINT tools (Maltego, SpiderFoot, Recon-ng) are powerful but built for analysts, not outcomes. Ayin unifies the full footprint into one **Exposure Score** and a remediation workflow, packaged for normal people first and security teams second — with safety and consent designed in, which the pro tools conspicuously lack.

**The bet.** The winner in this category is not the tool with the most data sources. It is the product that is **trusted** to hold the most sensitive query a person can make ("what's exposed about me?") and act on it responsibly. Trust architecture (Section 7) is the durable moat; data coverage is table stakes that competitors can match.

**The honest risk.** A person-search engine is one prohibited use away from being a stalking tool, and one careless feature from being a regulated consumer reporting agency under the FCRA. We treat both as existential and design against them from day one (Sections 7, 19, 20). This is also why "open OSINT with safeguards," not "open OSINT," is the model.

---

## 2. Problem & opportunity

### 2.1 The problem

Most people have a large, invisible digital footprint they did not consciously assemble and cannot see. It is spread across:

- **Data brokers** — hundreds of sites that buy, scrape, and resell name → address → phone → relatives → income, often without the person's knowledge.
- **Breaches & leaks** — credentials and personal data from thousands of historical breaches, plus "stealer log" dumps of malware-harvested sessions.
- **Self-published content** — social profiles, posts, photos, résumés, forum history, and side projects the person *did* put out there, but forgot the scale of.
- **Public records** — bounded but real: voter, property, court, business filings, depending on jurisdiction.
- **Inference** — the connective tissue: linking a username on one site to an email on another to a real name on a third.

The harm is concrete and rising: account takeover, SIM-swap, targeted phishing, doxxing and harassment, physical-safety risk for at-risk individuals (survivors of abuse, public figures, journalists), and social-engineering entry points into the companies people work for.

The core user pain is **not knowing**. People cannot defend against, or clean up, exposure they cannot see. The few who try face a fragmented mess: one tool for breaches, another for broker removal, manual searching for everything else, and no single picture of "how exposed am I, and what do I do first?"

### 2.2 Who feels it

- **Individuals** who had a scare (a breach notice, a spam-call surge, a stalker, a doxxing) or who are simply privacy-aware.
- **High-visibility individuals** — executives, founders, creators, politicians, journalists — for whom exposure is a safety and reputational issue.
- **Security teams** who must protect those executives and their broader workforce from social engineering that starts with OSINT.
- **Job seekers and the professionally cautious** who want to know what a recruiter or stranger sees first.

### 2.3 Why now

- **AI-amplified exploitation.** Personalized phishing, voice cloning, and deepfakes turn scattered public data into scalable attacks. Defensive footprint management moves from "nice to have" to "necessary."
- **Regulatory tailwinds.** The California Delete Act's DROP platform (live Jan 1, 2026; brokers must process requests on a 45-day cycle from Aug 1, 2026) plus state data-broker registries (CA, TX, OR, VT) create both consumer awareness and machine-readable rails for removal. Removal is becoming an API, not a letter-writing campaign.
- **Proven willingness to pay.** Data-removal incumbents validated that consumers pay $100–$250/year to reduce exposure — but they only solve one slice (brokers).
- **Market scale.** Removal services ~$1.68B (2024) → ~$7.99B (2033); OSINT ~$15.9B (2026) → ~$133.6B (2035). Ayin sits at the intersection of both.

### 2.4 The opportunity

Build the **system of record for personal digital exposure** — the place an individual or a security team goes to answer "what is exposed about this person, how bad is it, and what do we do?" — and own the recurring remediation + monitoring relationship that follows. The scan is the hook; monitoring and removal are the business.

---

## 3. Vision, mission & principles

**Vision.** A world where everyone can see their own digital shadow as clearly as an attacker can — and shrink it.

**Mission.** Give people and the teams that protect them a single, trustworthy view of their public exposure, and the tools to reduce it.

**Why "Ayin."** *Ayin* means "eye" — to see clearly. The brand promise is sight, not surveillance: we turn the asymmetry around so the person being looked at is the one holding the lens.

### Product principles

1. **Defense first.** Every feature is justified primarily by helping someone reduce *their own* or a legitimately-protected party's exposure. If a feature is more useful to a stalker than to a defender, it does not ship — or it ships only behind hard gates.
2. **Show, then shrink.** Discovery is worthless without remediation. We never leave a user staring at a scary report with no next step.
3. **Consent-forward, safeguards-always.** Self-scan and consented scans are the default and the easiest path. Third-party scans are allowed (open OSINT) but always gated by verification, purpose, rate limits, and audit.
4. **Sources, not assertions.** Every data point in a report is traceable to where it came from and when, with a confidence level. No mystery dossiers.
5. **Minimize what we keep.** We are in the business of *reducing* data exposure; we cannot be a hoarder. Aggressive retention limits, encryption, and a real "delete everything" path are part of the product, not the fine print.
6. **Not a verdict machine.** Ayin describes exposure. It does not score people's character, creditworthiness, or employability. That line (the FCRA line) is bright and we never cross it.
7. **Be removable from Ayin itself.** Anyone can demand exclusion from Ayin's index. The lens can be pointed away.

---

## 4. Goals & non-goals

### 4.1 Business goals (first 24 months)

| Horizon | Goal |
|---|---|
| MVP (M0–M3) | Ship self-scan; prove the "aha" — a person sees real, accurate exposure they didn't know about. Target activation ≥ 55% (scan completed → report viewed). |
| GA B2C (M4–M9) | Convert scan → paid monitoring/removal. Target ≥ 4–6% free→paid, > 90% gross monthly retention on paid. |
| Expansion (M10–M18) | Land first B2B design partners (exec protection); launch API beta. |
| Scale (M19–M24) | Repeatable B2B motion + B2C PLG flywheel; clear path to $5–10M ARR run-rate. |

### 4.2 Product goals

- A self-scan that returns a **useful, accurate, sourced** exposure report in minutes.
- A single **Exposure Score** people understand at a glance and that meaningfully drops as they remediate.
- A **remediation engine** that turns findings into actions (broker opt-outs, DROP/DSAR requests, hardening checklists) with tracked status.
- **Monitoring** that alerts on new exposure (new breach, new broker listing, new leaked credential).
- A **trust & safety layer** strong enough that we would be comfortable explaining any individual scan to a regulator or a journalist.

### 4.3 Non-goals (explicit — these define the safe edges of the product)

Ayin will **not**:

- **Be a consumer reporting agency or a background-check product.** No use for employment, tenant, credit, or insurance eligibility decisions. We build *procedures* to prevent this, not just a disclaimer (the FTC has been explicit that disclaimers alone are insufficient).
- **Do stranger facial recognition.** No "upload a face of someone you don't know and identify them." Image search is limited to *self/consented* image monitoring ("where does *my* photo appear?"). This rules out the Clearview-style use case deliberately.
- **Offer real-time location tracking** or anything that surfaces a person's live whereabouts.
- **Knowingly process data about minors** as scan subjects, beyond a parent/guardian managing their own dependents under verified-guardian controls.
- **Sell or resell the personal data it gathers.** Ayin is paid by the *subject* (or their authorized protector), not by anyone buying data about them. We are explicitly not a data broker in the data-selling sense, and we structure the company to keep it that way (Section 19).
- **Defeat platform protections.** No credential stuffing, no bypassing authentication, no scraping behind logins in violation of terms, no dark-web purchasing of stolen data. "Publicly available" has a strict definition (Section 11).
- **Aggregate into a permanent searchable dossier of the general public.** We scan on demand for a verified, purpose-bound requester and minimize retention; we are not building a people-search index for sale.

These non-goals are load-bearing. They are referenced again in pricing (what we won't sell), architecture (what we won't store), and compliance (Section 19).

---

## 5. Market & competitive landscape

### 5.1 Market sizing

| Market | Size | Trajectory | Relevance to Ayin |
|---|---|---|---|
| Personal data-removal services | ~$1.68B (2024) | → ~$7.99B by 2033, 18.2% CAGR | Direct B2C demand & willingness to pay |
| Open-Source Intelligence (OSINT) | ~$12.7B (2025), ~$15.9B (2026) | → ~$133.6B by 2035, 26.7% CAGR | The engine + B2B/enterprise demand |
| Adjacent: identity/breach monitoring | bundled into the above + identity-theft protection (multi-$B) | High growth | Monitoring revenue, bundling |

The serviceable wedge is the **consumer data-removal + breach-monitoring** spend (proven, growing ~18%/yr), with a far larger **OSINT/enterprise** expansion adjacency. Ayin's bottom-up TAM is "people and organizations who will pay to see and shrink personal exposure," which the incumbents show is real money today.

### 5.2 The four adjacent categories (and the gap)

The space is fragmented into four buckets, none of which does the whole job:

1. **Data-broker removal** — DeleteMe (~$104–199/yr), Optery (tiered Core/Extended/Ultimate, ~$3.99–$24.99/mo, covering 370 / 540 / 635+ brokers), Incogni (~$155/yr). They *only* address data brokers. They do not show breaches, social footprint, or give a unified exposure picture, and the "report" is mostly an opt-out worklist.
2. **Breach / credential checking** — Have I Been Pwned (free lookups; API from ~$3.50/mo; 12B+ records across 900+ sites; also ships an MCP server) and similar (DeHashed, stealer-log search). Excellent at breaches; nothing on brokers, social, or remediation beyond "change your password."
3. **Professional OSINT tooling** — Maltego (link analysis / graph), SpiderFoot (automated collection across 200+ sources), Recon-ng (modular CLI), Sherlock (username search across platforms), theHarvester, social-analyzer. Powerful and flexible, but built for trained analysts, output is raw, there's no remediation, and crucially **no built-in safety/consent layer** — they will happily profile anyone.
4. **People-search / background sites** — Spokeo, BeenVerified, etc. These are largely the *problem* (they're data brokers) and several flirt with FCRA exposure.

**The gap:** no one delivers *unified discovery (all four data types) → a single understandable score → tracked remediation → ongoing monitoring*, packaged for a normal person and a security team, with consent and safety as first-class design. That is Ayin.

### 5.3 Competitive matrix

| Capability | DeleteMe / Optery / Incogni | Have I Been Pwned | Maltego / SpiderFoot | People-search sites | **Ayin** |
|---|---|---|---|---|---|
| Data-broker exposure | ✅ | ❌ | partial | ✅ (they are brokers) | ✅ |
| Breach / credential exposure | partial | ✅ | partial | ❌ | ✅ |
| Social / public-web footprint | ❌ | ❌ | ✅ (raw) | partial | ✅ (synthesized) |
| Unified identity resolution | ❌ | ❌ | ✅ (manual) | partial | ✅ (automated) |
| Single exposure score | ❌ | ❌ | ❌ | ❌ | ✅ |
| Tracked remediation / removal | ✅ (brokers only) | ❌ | ❌ | ❌ | ✅ (brokers + DSAR + DROP + hardening) |
| Ongoing monitoring | ✅ | ✅ (notify) | ❌ | ❌ | ✅ |
| Built for non-experts | ✅ | ✅ | ❌ | ✅ | ✅ |
| Built for security teams / API | partial | ✅ (API) | ✅ | ❌ | ✅ (Phase 3+) |
| Consent & abuse safeguards | n/a (self only) | n/a (self only) | ❌ | ❌ (a liability) | ✅ (core) |

### 5.4 Positioning statement

> For privacy-conscious individuals and the security teams that protect people, **Ayin** is the digital-exposure scanner that shows your complete public footprint in one scored report and helps you shrink it — unlike data-removal tools that only fight brokers or OSINT tools built for analysts, Ayin unifies discovery, scoring, and remediation with consent and safety designed in.

### 5.5 Why we can win / moats

- **Outcome packaging.** Score + remediation + monitoring beats raw data dumps for the 99% who aren't analysts.
- **Trust as moat.** The brand permitted to hold "scan myself" queries at scale is hard to replicate; trust compounds and is destroyed by a single scandal — so incumbents built on data-selling can't easily follow us into consent-first.
- **Two-sided engine.** The same scanner powers cheap-CAC B2C PLG *and* high-ACV B2B; most competitors have only one motion.
- **Remediation data flywheel.** Every removal teaches us broker behavior, opt-out success rates, and re-listing patterns — improving our removal engine in ways pure-discovery tools can't match.
- **Regulatory alignment.** Building *with* DROP/DSAR rails (not against them) makes us more durable as regulation tightens, while people-search incumbents face growing legal headwinds.

---

## 6. Users & personas

### 6.1 B2C personas

**P1 — "The Spooked" (primary MVP persona).** Had a triggering event: a breach email, a wave of spam calls, a creepy DM, finding themselves on a people-search site. Non-technical. Wants reassurance and a clear to-do list. JTBD: *"Tell me how exposed I am and what to fix first, without making me an expert."* Success: completes a scan, understands the score, takes ≥ 1 remediation action.

**P2 — "The Privacy-Native."** Proactively manages their footprint, may already use a VPN, password manager, and maybe a removal service. Wants depth, control, and proof it's working. JTBD: *"Give me one place to see everything and automate the cleanup."* Success: subscribes to monitoring + removal, returns to watch the score drop.

**P3 — "The Exposed-by-Role."** Creator, founder, exec, journalist, or public-facing professional. Exposure is a safety/reputation risk; may have family to protect. Higher willingness to pay. JTBD: *"Find what an attacker or troll would use against me and my family, and keep watch."* Success: family plan + continuous monitoring; later a likely B2B/exec-protection lead.

**P4 — "The At-Risk."** Survivor of stalking/abuse, or otherwise targeted. Highest stakes, lowest tolerance for error, needs extreme care. JTBD: *"Help me disappear from the places that put me in danger."* This persona shapes our safety design more than our revenue model — protections for P4 (and ensuring Ayin can never be the *attacker's* tool against P4) are a design constraint, covered in Section 20. We will partner with advocacy orgs rather than market aggressively here.

### 6.2 B2B personas (Phase 3+)

**P5 — "The Protector" (security / exec-protection lead).** Owns the safety of named executives and sometimes the whole workforce. JTBD: *"Continuously find and remove exec exposure that enables social engineering, and report risk to leadership."* Buys seats + monitored identities; high ACV; values audit trails and SSO.

**P6 — "The Analyst" (SOC / fraud / trust & safety).** Investigates accounts, fraud rings, threat actors using OSINT today via Maltego/SpiderFoot. JTBD: *"Faster, cleaner identity resolution inside my workflow, via API, with an audit trail my legal team accepts."* Buys API volume.

**P7 — "The Vetted Investigator" (journalist, due-diligence, licensed PI).** Legitimate third-party-subject use. Highest abuse-adjacency, so the most gating: enhanced KYC, purpose attestation per matter, and tighter audit. We onboard these deliberately and slowly.

### 6.3 Persona → product mapping

| Persona | Primary value | Entry product | Monetization |
|---|---|---|---|
| P1 Spooked | Clarity + first fix | Free self-scan | Plus (monitoring) |
| P2 Privacy-native | One pane + automation | Free self-scan | Pro (monitoring + removal) |
| P3 Exposed-by-role | Family safety + watch | Free self-scan | Pro / Family |
| P4 At-risk | Safe removal | Assisted / NGO partner | Pro (often subsidized) |
| P5 Protector | Workforce/exec coverage | B2B pilot | Business / Enterprise seats |
| P6 Analyst | Fast resolution via API | API beta | Usage-based API |
| P7 Investigator | Lawful third-party scans | Vetted enterprise | Enterprise + per-matter |

---

## 7. The scan model & trust architecture (core)

This is the most important section in the document. It defines *who can scan whom, under what conditions* — the decision that separates a defensible privacy product from a liability. Everything in architecture, pricing, and compliance inherits from here.

### 7.1 The model: open OSINT, hard safeguards

Ayin can scan any individual from **publicly available** sources (the "open OSINT" choice). But no scan executes unless it passes a gated pipeline. Think of it as a series of locks, every one of which must open:

```
Requester identity verified  →  Subject-relationship / purpose declared  →
Eligibility & policy checks pass  →  Rate / volume limits OK  →
Scan runs (scoped to declared purpose)  →  Full audit record written  →
Subject-rights hooks available (notice, objection, exclusion)
```

If any lock fails, the scan is refused and logged. The point is that "anyone can be scanned" never means "anyone can scan anyone for any reason without a trace."

### 7.2 Scan types (consent tiers)

| Tier | Who the subject is | Verification required | Availability |
|---|---|---|---|
| **T0 — Self-scan** | The requester themselves | Identity verification that the requester *is* the subject (email/phone/SSO control; step-up for sensitive data) | All users; the default & the wedge |
| **T1 — Consented scan** | Someone who explicitly opted in | Subject's verified opt-in (e.g., employee enrolls in employer program; family member accepts invite) | Plus/Pro, Business |
| **T2 — Protected-party scan** | A person the requester is lawfully responsible for/protecting | Requester KYC + attested lawful basis (exec protection of named employees, guardian of dependent) | Business / Enterprise, contractually bound |
| **T3 — Lawful third-party scan** | A third party, no prior consent, lawful purpose | Enhanced KYC + per-matter purpose attestation + tighter rate limits + elevated audit + manual review thresholds | Enterprise / vetted only; onboarded individually |

The vast majority of volume (and all of MVP) is **T0**. T1–T2 unlock B2B. **T3 is the high-risk tier** and is deliberately the slowest to open, smallest in volume, most expensive, and most monitored. T3 is never self-serve.

### 7.3 The safeguards stack

Eight controls, each a product surface, not a policy PDF:

1. **Requester identity (KYC).** Real verification, scaled to tier: lightweight for T0 (prove control of the identifier you're scanning), full identity/business verification for T2–T3. Anonymous scanning of third parties is impossible by construction.
2. **Purpose limitation.** Every non-self scan requires a declared purpose from a controlled list (e.g., "protecting this named executive," "fraud investigation, case #"). The declared purpose scopes what the scan returns and is stored with the audit record. Free-text "other" routes to review, not auto-approval.
3. **Prohibited-use policy, enforced.** Stalking, harassment, intimate-partner surveillance, scanning minors, doxxing, and any FCRA-covered eligibility use are banned in the ToS *and* checked: subject-age signals, victim-protection lists, velocity/pattern detection, and known-abuse heuristics can block or hold a scan. (We learned from the FTC's *Filiquarian* action that a disclaimer is not a control — procedures are.)
4. **Rate & volume limits.** Per-account and per-tier caps on number of distinct subjects, scan frequency, and burst velocity. A consumer scanning dozens of *different* people is an abuse signal, not a power user. Cooldowns on repeat scans of the same third-party subject.
5. **Anomaly & abuse detection.** Behavioral models flag patterns consistent with stalking/bulk-profiling (many unique subjects, repeated scans of one non-self subject, scans clustered around a single address, off-pattern geography). Flags → throttle, step-up verification, hold-for-review, or ban.
6. **Immutable audit log.** Every scan records requester, verified identity, tier, declared purpose, subject identifiers, sources touched, timestamp, and result. Tamper-evident, retained for a defined window, producible to the subject (on a verified rights request) and to regulators. This is also a B2B selling point.
7. **Subject rights & notice.** Data-subject access, objection, and erasure flows. For T2/T3, configurable subject-notification. A public **"Exclude me from Ayin"** mechanism (verify identity → we suppress you as a scan subject and purge cached data). The lens can always be pointed away.
8. **Data minimization & retention.** Default-short retention of raw scan artifacts; store findings and the score, not a permanent dossier. Encryption everywhere; a real "delete my account and all data" path. We don't keep what we don't need, and we never build a sellable index.

### 7.4 The regulatory posture this creates (summary; full detail in §19)

- **FCRA:** Ayin is *not* a consumer reporting agency and forbids FCRA-covered uses, backed by user verification, purpose checks, and monitoring — not just a notice. Reports carry no eligibility scoring.
- **GDPR:** Lawful basis is the requester's/our **legitimate interest** for defensive scanning, with a documented Legitimate Interest Assessment and balancing test; "publicly available" is defined narrowly (accessible without login / not behind a contact-gate). Full data-subject rights honored.
- **CCPA/CPRA + Delete Act:** We honor consumer deletion, register where required, and **integrate DROP** so users can fire deletion at registered brokers — turning regulation into a feature.
- **"Are we a data broker?"** Possibly, by some state definitions, since we process data about people we have no direct relationship with. We plan for it: register where required (CA/TX/OR/VT), but structurally avoid the *selling* that the laws most target, and honor DROP ourselves.

### 7.5 Why safeguards are the moat, not the tax

A naïve competitor sees these eight controls as friction that slows signup and shrinks the addressable use cases. That is exactly backwards. The controls are what let us hold the most sensitive query on the internet — *"what's exposed about me?"* — and be trusted with the answer. Trust is the asset that compounds and the asset a single scandal destroys; building it in from the first commit is cheaper than retrofitting it after the first headline, and impossible for a data-selling incumbent to copy without dismantling their own business model.

---

## 8. Product overview & capabilities

### 8.1 The scan lifecycle

Ayin is one pipeline expressed in increasingly capable surfaces:

```
1. INPUT        Seed identifiers (name, email, phone, username, location, photo of self)
2. DISCOVERY    Query data sources across modules (breach, broker, social, records, image)
3. RESOLUTION   Entity-resolve candidates into one confident identity; discard non-matches
4. ENRICHMENT   Normalize, dedupe, classify sensitivity, attach source + confidence
5. SCORING      Compute the Exposure Score and category breakdowns
6. REPORT       Present findings: what's out there, where, how risky, why it matters
7. REMEDIATION  Convert findings to tracked actions (opt-outs, DSAR/DROP, hardening)
8. MONITORING   Re-run on schedule; alert on new/changed exposure; show score trend
```

MVP implements 1–6 for **self-scan**; 7–8 are the paid expansion. The lifecycle never changes; later phases deepen each step and open more tiers.

### 8.2 Capability modules

| Module | What it finds | Primary sources (see §11) | Phase |
|---|---|---|---|
| **Identity graph** | Links seed identifiers into one resolved person; surfaces aliases/usernames | Username search, cross-source correlation | MVP |
| **Breach & credential exposure** | Breached accounts, exposed credentials, pastes, stealer-log mentions | HIBP-class breach APIs, paste/leak indexes | MVP |
| **Public-web & social footprint** | Public profiles, posts, mentions, bios, photos *the person published* | Search APIs, public social endpoints | MVP (read-only) |
| **Data-broker presence** | Listings on people-search/broker sites (name, address, phone, relatives) | Broker index, targeted lookups | MVP (detect) → Phase 2 (remove) |
| **Public records (bounded)** | Voter/property/court/business filings where lawfully public | Licensed/public record providers | Phase 2 |
| **Image / likeness (self only)** | Where the user's *own* photo appears publicly | Consented reverse-image search | Phase 2 |
| **Technical / attack-surface** (B2B) | Exec emails, domains, leaked tokens tied to a person/org | Domain/breach/tech intel | Phase 3 |

### 8.3 The Exposure Score

A single 0–100 score (higher = more exposed) with category sub-scores (Credentials, Brokers, Social, Records, Identity-linkage). Properties that make it good:

- **Explainable.** Every point traces to specific findings; tapping the score shows what drives it.
- **Actionable.** Each contributor maps to a remediation; the score is a to-do list ranked by impact.
- **Responsive.** It drops as the user remediates, giving a visible win and a reason to stay subscribed.
- **Honest.** It measures *exposure and exploitability*, never the person. It is explicitly not a trust/credit/character score (FCRA line).

Scoring weights findings by sensitivity (a live exposed password ≫ a public LinkedIn), recency, exploitability, and corroboration. The rubric lives in Appendix 23.3 and is versioned (score changes from new data vs. methodology changes are labeled differently so trends stay meaningful).

### 8.4 The remediation engine

Findings become tracked actions:

- **Broker opt-outs** — automated/assisted removal requests; status tracked (requested → acknowledged → removed → re-listing watch).
- **DROP & DSAR** — generate and route deletion requests to registered brokers via California's DROP and standard DSAR templates for other jurisdictions.
- **Account hardening** — guided steps for breached accounts (rotate password, enable MFA, revoke sessions), prioritized by the score.
- **Self-publishing cleanup** — guidance/links to lock down or remove the user's *own* posts, profiles, and old content.

Each action shows expected score impact, so users do the high-value things first.

### 8.5 Monitoring

Continuous (or scheduled) re-scan with alerting: new breach inclusion, new broker listing or re-listing after removal, new leaked credential, new high-risk public exposure. Delivered via email/push/Slack (B2B), with a dashboard showing the score trend over time — the proof that the subscription is working.

---

## 9. Functional requirements (feature specs)

Requirements are grouped by area, each with priority (P0 = MVP, P1 = B2C GA, P2 = expansion, P3 = B2B), a representative user story, and acceptance criteria. IDs are stable references for the roadmap and tickets.

### 9.1 Onboarding, identity & accounts

**FR-AUTH-1 (P0) — Account creation & self-identity verification.**
*Story:* As a new user, I can create an account and prove control of the identifiers I want to scan, so my self-scan is legitimate and private.
*Acceptance:* Email/OAuth signup; verify control of each seed identifier (email link, phone OTP); cannot view sensitive results for an identifier until control is verified; step-up verification before revealing credential-level data.

**FR-AUTH-2 (P0) — Consent & ToS gate.**
*Story:* Before my first scan I must accept the terms, including prohibited uses, so expectations are explicit.
*Acceptance:* Versioned ToS/AUP acceptance recorded with timestamp; scan blocked until accepted; re-prompt on material changes.

**FR-AUTH-3 (P3) — Org accounts, SSO, RBAC.**
*Story:* As a security admin, I can manage seats, SSO (SAML/OIDC), and roles, so my team uses Ayin under enterprise controls.
*Acceptance:* SSO login; roles (admin/analyst/viewer); per-role scan-tier permissions; seat management; audit export.

**FR-AUTH-4 (P2) — Requester KYC (tiered).**
*Story:* To run non-self scans, I complete identity/business verification appropriate to the tier.
*Acceptance:* T1 consent capture; T2 business verification + contract; T3 enhanced KYC + per-matter purpose; tier unavailable until verification passes.

### 9.2 Scan configuration & execution

**FR-SCAN-1 (P0) — Start a self-scan.**
*Story:* I enter what I know about myself (name, emails, phones, usernames, city) and start a scan.
*Acceptance:* Accepts multiple seed identifiers; validates/normalizes them; shows what will be searched and an ETA; runs asynchronously with progress.

**FR-SCAN-2 (P0) — Scan tiering & purpose declaration.**
*Story:* For any non-self subject, I must select a scan tier and declare a purpose.
*Acceptance:* Self-scan default for own verified identifiers; non-self requires tier + purpose from controlled list; purpose stored in audit; disallowed purpose → refusal with explanation.

**FR-SCAN-3 (P0) — Rate/volume enforcement.**
*Acceptance:* Per-tier caps on unique subjects/day, scan frequency, burst velocity; cooldown on repeat non-self subject; clear messaging when limited; limits configurable server-side.

**FR-SCAN-4 (P1) — Re-scan & scheduling.**
*Acceptance:* Manual re-scan; scheduled re-scan (daily/weekly/monthly by plan); diff vs. previous scan computed.

**FR-SCAN-5 (P0) — Scan refusal & safety hold.**
*Acceptance:* Scans matching abuse heuristics (minor subject signals, victim-protection match, anomaly flag) are refused or held for review; reason logged; appeal path for false positives.

### 9.3 Discovery & data sources

**FR-DISC-1 (P0) — Breach & credential discovery.**
*Acceptance:* Query breach/leak sources for each verified email/phone/username; return breach name, date, data classes, and exploitability; never display full plaintext stolen passwords (show exposure status / partial only).

**FR-DISC-2 (P0) — Public-web & social discovery.**
*Acceptance:* Find public profiles/mentions for seeds via compliant search/public endpoints; capture URL, platform, snippet, captured-at; respect robots/ToS and the "publicly available" definition (§11).

**FR-DISC-3 (P0) — Data-broker detection.**
*Acceptance:* Detect presence on supported broker/people-search sites; record site, listing URL, exposed fields; flag as removable.

**FR-DISC-4 (P0) — Source connector framework.**
*Acceptance:* Pluggable connector interface (auth, rate-limit, normalize, error/backoff, ToS metadata); connectors are independently enable/disable-able and versioned; per-connector health and cost telemetry.

**FR-DISC-5 (P2) — Public records & consented image search.**
*Acceptance:* Bounded public-record lookups via licensed providers with jurisdiction labels; reverse-image search restricted to the user's own/consented images, never stranger identification.

### 9.4 Entity resolution & enrichment

**FR-ER-1 (P0) — Identity resolution.**
*Story:* Ayin should merge "the same me" across sources and not mix me up with a namesake.
*Acceptance:* Probabilistic matching across identifiers with confidence; candidates below threshold are excluded or shown as "possible, unconfirmed"; user can confirm/reject matches; no auto-merge of low-confidence records into the profile.

**FR-ER-2 (P0) — Dedupe, classify, attribute.**
*Acceptance:* Deduplicate findings; classify by category and sensitivity; every finding carries source, captured-at, and confidence; conflicting data flagged, not silently merged.

**FR-ER-3 (P1) — Identity graph view.**
*Acceptance:* Visualize resolved identifiers and links with confidence; expand/collapse; export (paid).

### 9.5 Scoring & reporting

**FR-SCORE-1 (P0) — Exposure Score.**
*Acceptance:* 0–100 score + category sub-scores from a versioned rubric; tap-through to contributing findings; recompute on each scan; methodology version labeled.

**FR-REPORT-1 (P0) — Exposure report.**
*Acceptance:* Findings grouped by category, ranked by risk; each shows what/where/why-it-matters/recommended action; plain-language summary up top; empty/low-exposure states handled gracefully.

**FR-REPORT-2 (P1) — Shareable/exportable report.**
*Acceptance:* PDF/link export (paid); redaction controls; expiring links; watermark + audit of exports.

**FR-REPORT-3 (P3) — B2B aggregate reporting.**
*Acceptance:* Org dashboard of monitored identities, aggregate exposure, trend, and per-identity drill-down; exportable for leadership.

### 9.6 Remediation

**FR-REM-1 (P1) — Broker opt-out workflow.**
*Acceptance:* One-click/assisted opt-out per detected broker; status lifecycle (requested→ack→removed→re-listing watch); evidence stored; SLA/expectation shown.

**FR-REM-2 (P1) — DROP & DSAR generation.**
*Acceptance:* Generate California DROP deletion requests and jurisdiction-appropriate DSAR letters; track delivery and response; surface the 45-day broker processing cycle.

**FR-REM-3 (P0 lite → P1 full) — Hardening checklist.**
*Acceptance:* Per-finding hardening steps (rotate password, enable MFA, revoke sessions, lock down profile) with expected score impact and done-tracking. (A read-only checklist ships in MVP; tracking in P1.)

**FR-REM-4 (P1) — Score-impact ranking.**
*Acceptance:* Actions sorted by expected score reduction × ease; "do this first" guidance.

### 9.7 Monitoring & alerts

**FR-MON-1 (P1) — Continuous monitoring.**
*Acceptance:* Scheduled re-scans by plan; detect new/changed exposure; persist history.

**FR-MON-2 (P1) — Alerting.**
*Acceptance:* Configurable alerts (email/push; Slack/webhook for B2B) on new breach, new/re-listed broker entry, new leaked credential; severity-tagged; dedup/digest to avoid fatigue.

### 9.8 Trust, safety & rights (cross-cutting, mostly P0)

**FR-TS-1 (P0) — Immutable audit log** of every scan (requester, identity, tier, purpose, subject, sources, result, timestamp); tamper-evident; queryable; exportable (B2B).

**FR-TS-2 (P0) — Abuse detection & response** (velocity, unique-subject, pattern heuristics) → throttle/step-up/hold/ban; review queue; reviewer tooling.

**FR-TS-3 (P0) — "Exclude me from Ayin"** public flow: verify identity → suppress as scan subject + purge cached data; honored across future scans.

**FR-TS-4 (P0) — Data-subject rights**: access, objection, deletion; account self-service "delete everything"; retention timers auto-purge raw artifacts.

**FR-TS-5 (P1) — Transparency reporting**: periodic public report (scan volumes by tier, refusals, abuse actions, exclusion requests honored).

---

## 10. System architecture

### 10.1 Architectural principles

- **Scan-as-pipeline.** The eight-step lifecycle is an orchestrated, asynchronous, resumable job — not a synchronous request. Sources are slow, rate-limited, and flaky; the system is built around that reality.
- **Connectors are isolated & swappable.** Each data source sits behind a uniform connector contract so we can add, version, throttle, or kill a source without touching the core.
- **PII is a vault, not a database.** Sensitive subject data lives in an encrypted, access-controlled, short-retention store, separate from operational data. The default is to keep findings + score, not raw artifacts.
- **Safety is in the critical path.** KYC, purpose, rate-limit, and abuse checks are pipeline gates that can refuse a job — not async side-effects.
- **Auditability is non-negotiable.** Every scan and data access writes an immutable record.

### 10.2 High-level component diagram

```
                         ┌──────────────────────────────┐
   Web app (B2C) ─────►  │           API Gateway          │
   B2B console  ─────►   │  authn/z · tiering · rate-limit │
   Public API   ─────►   └───────────────┬────────────────┘
                                          │
        ┌─────────────────────────────────┼─────────────────────────────────┐
        ▼                                 ▼                                  ▼
 ┌────────────┐                  ┌──────────────────┐               ┌────────────────┐
 │  Identity   │                 │  Scan Orchestrator│               │ Trust & Safety  │
 │  & KYC svc  │◄───purpose/────►│  (job state mach.) │◄──gate checks►│  (abuse, rules, │
 └────────────┘    tier checks   └─────────┬─────────┘               │   review queue) │
                                            │                          └───────┬────────┘
                              dispatch jobs │                                   │
                                            ▼                                   ▼
                                 ┌────────────────────┐                ┌────────────────┐
                                 │  Connector workers  │                │   Audit log     │
                                 │ (breach│social│broker│                │ (append-only)   │
                                 │  records│image│tech) │                └────────────────┘
                                 └─────────┬──────────┘
                                           ▼
                            ┌─────────────────────────────┐
                            │  Entity Resolution & Enrich   │
                            │  (match · dedupe · classify)  │
                            └─────────────┬─────────────────┘
                                          ▼
              ┌───────────────┐   ┌────────────────┐   ┌───────────────────┐
              │ Scoring engine │  │  PII vault      │   │ Remediation engine │
              │ (Exposure Score)│ │ (encrypted,     │   │ (opt-out·DROP·DSAR │
              └───────┬─────────┘ │  short-retain)  │   │  ·hardening tasks) │
                      │           └────────────────┘   └─────────┬─────────┘
                      ▼                                            ▼
              ┌────────────────┐                          ┌────────────────┐
              │ Report service  │                          │ Monitoring &    │
              │ (render·export) │                          │ alerting (cron) │
              └────────────────┘                          └────────────────┘
```

### 10.3 Component responsibilities

| Component | Responsibility |
|---|---|
| **API gateway** | AuthN/Z, request validation, tier resolution, rate limiting, per-key quotas |
| **Identity & KYC service** | Verifies requester identity and (for self-scan) control of seed identifiers; tier-appropriate KYC; consent records |
| **Scan orchestrator** | Owns the job state machine (queued→gated→running→resolving→scoring→done/failed/held); retries, backoff, partial results, resumability |
| **Trust & Safety engine** | Pre-scan gates (purpose, prohibited-use, rate, anomaly), real-time abuse scoring, review queue, enforcement actions |
| **Connector workers** | Per-source fetchers behind the uniform connector contract; respect source rate limits, ToS metadata, caching, cost accounting |
| **Entity resolution & enrichment** | Probabilistic matching, dedup, sensitivity classification, source/confidence attribution |
| **Scoring engine** | Versioned Exposure Score + sub-scores; explainability links |
| **PII vault** | Encrypted store for sensitive findings/artifacts; field-level access control; retention timers; crypto-shred on delete |
| **Report service** | Renders reports/dashboards; export with redaction, watermark, expiring links |
| **Remediation engine** | Opt-out automation, DROP/DSAR generation & tracking, hardening task management |
| **Monitoring & alerting** | Scheduled re-scans, diffing, alert routing, digesting |
| **Audit log** | Append-only, tamper-evident record of scans and data access |

### 10.4 Data model (core entities, simplified)

- **User / Org** — account, plan, roles, KYC status.
- **Subject** — the person being scanned (often = user for T0); identifiers; exclusion status.
- **Identifier** — email / phone / username / name+location / image-hash; verification state; confidence.
- **Scan** — tier, declared purpose, requester, subject, status, source set, timestamps, audit ref.
- **Finding** — atomic exposure (one breach hit, one broker listing, one public profile): category, sensitivity, source, captured-at, confidence, exploitability, current state.
- **Score** — overall + sub-scores, rubric version, contributing-finding refs, computed-at.
- **RemediationTask** — type (opt-out/DROP/DSAR/hardening), target, status lifecycle, evidence, expected & realized score impact.
- **AuditRecord** — immutable; the spine of trust & compliance.
- **AbuseSignal / ReviewCase** — safety telemetry and human-review workflow.

### 10.5 Reference tech stack (proposed, not dogmatic)

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | TypeScript + React/Next.js | Fast iteration, SSR for marketing/SEO, shared types |
| API | TypeScript (NestJS) or Python (FastAPI) | Pick the team's strength; FastAPI pairs well with ML/ER work |
| Orchestration | Temporal (or a durable queue: SQS/Celery/BullMQ) | Long-running, resumable, retryable scan jobs are exactly Temporal's sweet spot |
| Workers | Python | Best ecosystem for scraping, parsing, ML, ER |
| Datastores | Postgres (operational) · object storage (artifacts) · OpenSearch (search/findings) · Redis (cache/rate-limit) | Boring, proven; Postgres-first |
| PII vault | Dedicated encrypted store + KMS, field-level keys | Separation + crypto-shred for "delete everything" |
| Identity graph | Start relational/edge tables; add a graph DB (Neo4j) only if resolution complexity demands it | Avoid premature graph-DB cost |
| ML/ER | Python (record-linkage libs, embeddings) + an LLM for synthesis/classification | Use ML where it earns its keep; rules first |
| Infra | Cloud (AWS/GCP), containers (K8s or ECS), IaC (Terraform) | Standard, hireable |
| Observability | OpenTelemetry, centralized logs/metrics, per-connector cost dashboards | COGS visibility is existential (data costs) |

### 10.6 AI/ML usage — and its guardrails

LLMs/ML are used where they add leverage, never as an unaccountable oracle:

- **Synthesis** — turn raw findings into plain-language report narratives and "why this matters."
- **Classification** — sensitivity tagging, category assignment, dedup assistance.
- **Entity resolution assist** — embeddings/similarity to propose matches (rules + thresholds still gate auto-merge).
- **Guardrails:** LLMs never invent findings — they only describe data already gathered and cited; every AI-surfaced claim links to a source finding; no AI-generated speculation about a person's character, behavior, or anything eligibility-adjacent (FCRA line); prompts and outputs for non-self subjects are subject to the same audit. Hallucination here isn't a UX bug, it's a defamation/safety risk, so synthesis is constrained to retrieved, sourced facts.

### 10.7 Security architecture

Encryption in transit and at rest; field-level encryption for the PII vault with per-subject keys enabling crypto-shred; least-privilege access with all PII access audited; secrets in a managed vault; tenant isolation for B2B; SSDLC with dependency scanning, secret scanning, and pre-launch pen tests; SOC 2 Type II and ISO 27001 as Phase-3 gating for enterprise (Section 19). Internal access to subject data is itself a "scan" for audit purposes — staff are not exempt from the trust model.

### 10.8 Scalability & cost control

Scans are bursty and source-bound, so: queue-based backpressure, aggressive per-source caching (don't re-pull an unchanged breach corpus per user), tier-aware concurrency, and **per-connector cost accounting wired into COGS** (paid data APIs are the dominant variable cost — see §17). Monitoring re-scans are diff-first to avoid full re-pulls. Source spend has hard budget guards so a pricing/usage mismatch can't quietly destroy margin.

---

## 11. Data sources & acquisition strategy

### 11.1 Definition of "publicly available" (the line we don't cross)

A source is in-scope only if it is **accessible to anyone without authenticating, without defeating a technical control, and without violating the source's terms.** Concretely:

- ✅ In scope: open breach-exposure APIs, public search results, social content visible without login and not behind a contacts-gate, lawfully public records via licensed providers, broker listings shown publicly.
- ❌ Out of scope: anything behind a login we don't own, anything requiring credential stuffing or auth bypass, purchased stolen data / dark-web buys, content visible only to a person's contacts, scraping in violation of ToS, data about minors.

This mirrors the GDPR reading that social data is "public" only when visible to everyone without login. The definition is enforced in the connector contract (each connector declares its legal basis and access method) and reviewed by counsel before a source ships.

### 11.2 Source tiers

| Tier | Examples (illustrative) | Acquisition | Notes |
|---|---|---|---|
| **A — Breach/credential** | HIBP-class breach APIs (12B+ records, 900+ sites; API ~$3.50/mo entry, also ships an MCP server), paste/leak indexes, stealer-log *exposure* checks | Licensed API | Never display full stolen secrets; show exposure status. No buying dumps. |
| **B — Public web / search** | Search APIs, public profile endpoints | API + compliant fetch | Respect robots/ToS; cache; rate-limit |
| **C — Data-broker / people-search** | Broker index + targeted public-listing detection | Detection via public pages; removal via opt-out/DROP | We *detect to remove*, not to resell |
| **D — Public records** | Voter/property/court/business filings | Licensed record providers | Jurisdiction-bounded; labeled; Phase 2 |
| **E — Image (self/consented)** | Reverse-image search of the user's own images | Licensed API, consented only | No stranger identification, ever |
| **F — Technical/attack-surface (B2B)** | Domain/email/leaked-token intel | API/partners | Phase 3; org-scoped |

### 11.3 Build vs. buy vs. partner

- **Buy/partner** for breach data, search, records, and image — these are commodity-with-moat datasets where building from scratch is wasteful and legally fraught. Negotiate volume terms early; abstract behind connectors so we're never single-source-locked.
- **Build** the connector framework, entity resolution, scoring, remediation, and trust/safety — this is the proprietary core and the moat.
- **Hybrid** on broker coverage: maintain our own broker registry/playbooks (which sites, what fields, how to opt out, re-listing behavior) — this operational dataset compounds and is hard to copy (the remediation flywheel).

### 11.4 Source governance

Every connector carries metadata: legal basis, access method, ToS reference, data classes returned, cost per call, rate limits, and a counsel sign-off flag. A source cannot be enabled in production without that record complete. Sources are reviewed periodically; if a source changes terms or becomes non-compliant, the connector is disabled centrally and findings sourced from it are flagged. This governance is also what lets us answer "where did this data point come from?" for any finding.

### 11.5 Coverage strategy over time

Start narrow and trustworthy (breach + a focused set of high-impact brokers + public search) and expand coverage as a *measured* function of remediation value, not vanity counts. Optery-style "we cover 635+ brokers" is a marketing axis we'll meet over time, but our wedge is **completeness across categories** (breach + social + broker + records in one score), which no single competitor offers, rather than maximal broker count alone.

---

## 12. UX & key flows

### 12.1 Design tenets

- **Calm, not alarmist.** Findings can frighten; the UI leads with "here's the plan," not a wall of red. (Safety-relevant for P4.)
- **One number, then depth.** The Exposure Score is the hero; everything expands from it.
- **Every finding has a verb.** No dead-end facts; each finding links to an action or an explanation.
- **Progress is visible.** The score trend and remediation checklist make the subscription's value self-evident.
- **Privacy of the product itself is obvious.** Show how little we keep, how to delete, how to exclude — trust is UX, not just policy.

### 12.2 Core flows

**Flow A — First self-scan (P0, the activation moment).**
1. Sign up → accept ToS/AUP.
2. Enter seeds (name, email(s), phone(s), username(s), city). Verify control of each.
3. "Here's what we'll check and why" → start scan (async, progress shown; partial results stream in).
4. Report: Exposure Score + category breakdown + top findings, each with a recommended action.
5. CTA: "Fix your top 3" (free hardening checklist) and "Watch for new exposure" (upgrade to monitoring).
*Success metric:* scan completed → report viewed (activation), ≥ 1 action started.

**Flow B — Remediation (P1).**
Findings → ranked action list by score impact → execute (broker opt-out / DROP / DSAR / hardening) → track status → watch score drop. Re-listing watch reopens a task if a broker re-adds the user.

**Flow C — Monitoring & alerts (P1).**
Dashboard with score-over-time; alert on new exposure; each alert deep-links to the new finding and its action. Digesting prevents fatigue.

**Flow D — "Exclude me from Ayin" (P0, public).**
Anyone (user or not) → verify identity → confirm suppression → cached data purged, future scans suppress them. Confirmation + audit record. This flow is publicly linked from the site footer, not buried.

**Flow E — B2B console (P3).**
Admin enrolls monitored identities (with the right tier/consent) → org dashboard of aggregate exposure + per-identity drill-down → alerts to Slack/SIEM → leadership-ready export. SSO, RBAC, and audit export throughout.

**Flow F — Vetted third-party scan (T3, Enterprise only, P4).**
Verified investigator → opens a "matter" → declares purpose & legal basis → scan scoped to purpose → elevated audit + possible manual review → results time-boxed and matter-bound. Deliberately high-friction.

---

## 13. The MVP (in depth)

### 13.1 MVP thesis

> Prove that a non-technical person will give us a few identifiers, receive a **clear, accurate, sourced** picture of their exposure across *more than one category*, understand the single score, and take at least one action — and that enough of them want ongoing protection to justify building the paid engine.

The MVP exists to validate the **"aha"** (seeing real exposure they didn't know about) and the **pull toward protection** (monitoring/removal demand). It is **T0 self-scan only.** No third-party scanning ships in the MVP — that removes the entire high-risk surface while we prove value, and keeps the first build legally simple.

### 13.2 In scope (MVP)

- **Account + self-identity verification** (FR-AUTH-1, FR-AUTH-2).
- **Self-scan** across three categories: **breach/credential, public-web/social, data-broker detection** (FR-SCAN-1/2/3/5, FR-DISC-1/2/3/4).
- **Entity resolution (basic)** to merge a user's own verified identifiers and avoid namesake mixing (FR-ER-1/2).
- **Exposure Score + report** with sourced, ranked findings and plain-language summary (FR-SCORE-1, FR-REPORT-1).
- **Hardening checklist (read-only)** with expected score impact (FR-REM-3 lite).
- **Broker detection → manual opt-out guidance** (links + instructions; *automated* removal is Phase 2).
- **Trust & safety floor:** ToS/AUP gate, rate limits, abuse refusal, audit log, "Exclude me from Ayin," delete-everything, short retention (FR-TS-1/2/3/4).
- **Waitlist/intent capture for monitoring + removal** (measures pull without building the engine yet).

### 13.3 Explicitly out of scope (MVP)

- Any non-self scan (T1–T3), org accounts, SSO, API.
- Automated broker removal, DROP/DSAR automation (we *show* the opportunity and capture intent).
- Continuous monitoring/alerting (we capture demand; the engine is Phase 1/2).
- Public records, image search, technical/attack-surface modules.
- Identity-graph visualization, exports, B2B dashboards.
- Payment at scale (a simple paid pre-order/founding plan is optional to test willingness-to-pay; full billing is Phase 1).

### 13.4 Why this is the right cut

It delivers the full *value loop minus automation*: discover → resolve → score → report → (manual) act. It ships the **non-negotiable safety floor** (self-only + audit + exclusion + rate limits) so we never trade safety for speed. And it makes the paid thesis measurable: if people complete scans, understand scores, act, and ask for monitoring/removal, the business is real. Everything cut from the MVP is *automation and expansion of the same loop* — nothing in the MVP will be thrown away or contradicted later (alignment requirement satisfied: MVP ⊂ PRD).

### 13.5 MVP architecture (lean version of §10)

- Monolith-friendly: one API service + a worker pool + Postgres + object storage + Redis. Defer Temporal if a simple durable queue (BullMQ/Celery) suffices for 3 connectors; keep the **connector contract** from day one so sources stay swappable.
- Three connectors only: **breach API, search/public-social, broker-detection.** Each implements the uniform contract (auth, rate-limit, normalize, cost telemetry, ToS metadata).
- Entity resolution: rules + thresholds (defer heavy ML); operate only over the user's *own verified* identifiers, which is a far easier matching problem than open resolution.
- PII vault discipline from the start (encryption, retention timers, crypto-shred) — cheap to do early, painful to retrofit.
- Audit log from the first scan — also cheap early, foundational forever.

### 13.6 MVP data sources

Start with **one breach provider** (HIBP-class — proven, ~$3.50/mo entry, 12B+ records, MCP server available for fast integration), **one search/public-web method** (compliant search API), and **a hand-curated set of ~20–50 high-impact US data brokers** for detection (the ones that drive the most spam/exposure), with documented manual opt-out instructions. Depth of *categories* over breadth of *brokers* is the MVP differentiator.

### 13.7 MVP success criteria (go/no-go to Phase 1)

| Metric | Target | Why |
|---|---|---|
| Scan completion (start→report) | ≥ 70% | The core experience works |
| Activation (report viewed + understood) | ≥ 55% | The "aha" lands |
| Findings accuracy (sampled, manually QA'd) | ≥ 90% precision on shown findings | Trust depends on not crying wolf |
| ≥ 1 remediation action started | ≥ 40% of activated | "Show, then shrink" resonates |
| Monitoring/removal intent (waitlist/pre-order) | ≥ 25% of activated | Paid thesis is real |
| Safety: zero non-self scans; 100% scans audited | hard gate | Non-negotiable |
| Qualitative: "I learned something I didn't know" | majority in interviews | Validates the wedge |

Falsifiable kill-criteria: if accuracy can't clear ~90% without heroics, or activation stalls below ~35% after iteration, we rethink the wedge before building the paid engine.

### 13.8 MVP build plan (~12 weeks, small team)

| Weeks | Milestone | Output |
|---|---|---|
| 0–2 | Foundations | Repo, infra/IaC, auth, ToS gate, audit log skeleton, connector contract |
| 2–5 | Discovery | Breach + search + broker-detection connectors; scan orchestrator (queue-based); PII vault |
| 5–7 | Resolution + scoring | Self-identifier resolution; Exposure Score v0 + rubric; finding store |
| 7–9 | Report + safety | Report UI, plain-language summary, hardening checklist; rate limits, abuse refusal, exclude-me, delete-everything |
| 9–11 | Polish + instrument | Onboarding, empty/low-exposure states, analytics, accuracy QA harness |
| 11–12 | Private beta | Invite cohort, measure §13.7, interview users, decide go/no-go |

Team for MVP: 2 backend, 1 frontend, 1 design (PT), founder/PM, fractional counsel for source + ToS sign-off. (See §21.)

### 13.9 Pre-MVP "concierge" option (optional, de-risks weeks 0–6)

Before automating, run 25–50 **manual scans** for recruited users (analyst assembles the report by hand using the same sources, delivered in Ayin's report format). This validates accuracy, the report design, the "aha," and willingness-to-pay with near-zero build — and seeds the broker playbook and scoring rubric with real data. Strictly self/consented subjects only, same safety rules.

---

## 14. Roadmap

Phases map 1:1 to pricing tiers (§16) and personas (§6) so the business stays coherent.

| Phase | Timeline | Theme | Ships | Unlocks (persona / revenue) |
|---|---|---|---|---|
| **P0 — MVP** | M0–M3 | Prove the scan | Self-scan, 3 categories, score, report, safety floor, intent capture | P1; validation |
| **P1 — B2C GA** | M4–M9 | Make it a product | Billing, continuous monitoring + alerts, broker opt-out automation, DROP/DSAR, full hardening tracking, exports | P1/P2/P3; Plus & Pro revenue |
| **P2 — Depth & family** | M7–M12 | Widen coverage & accounts | Public records, consented image monitoring, family plans, identity-graph view, re-listing watch | P3; Family/Pro ARPU |
| **P3 — B2B** | M10–M18 | Two-sided engine | Org accounts, SSO, RBAC, T1/T2 scans, exec/workforce monitoring, B2B dashboards, SOC 2 | P5; Business/Enterprise ACV |
| **P4 — Platform** | M16–M24 | Scale & ecosystem | Public API (T0/T1) + usage billing, webhooks/SIEM, vetted T3 program, integrations marketplace | P6/P7; API & enterprise |

Sequencing logic: nail B2C value and the safety floor (P0–P1) → deepen ARPU and retention (P2) → only then open third-party tiers and B2B (P3), because those carry the compliance/abuse load and should sit on a proven, trusted core. API and T3 come last, when monitoring, audit, and abuse-detection are battle-tested.

---

## 15. Go-to-market

### 15.1 Wedge & motion

**B2C product-led growth first.** The free self-scan is the top of funnel: high intent ("am I exposed?"), inherently shareable (your score), and a natural upgrade to monitoring/removal. Low CAC because the product *is* the demo. The B2B motion is layered on later, fed by P3 users (execs/founders who first scanned themselves) and outbound to security teams.

### 15.2 B2C channels

- **SEO / content** — the category is search-driven ("remove my info from [broker]", "was my email breached", "how to delete myself from the internet"). Build the authoritative, genuinely-useful library (and capture the DROP/Delete-Act wave). This is the cheapest durable channel and compounds.
- **Free tools / "scan yourself"** — the scan itself, plus standalone micro-tools (breach check, "what brokers list you") as link-worthy lead magnets.
- **Trust-led PR & partnerships** — privacy advocates, security creators, journalists; partner (don't market aggressively) with anti-stalking/DV orgs for the at-risk persona — credibility and the right kind of attention.
- **Referral** — "share your score / invite family" with privacy-safe mechanics.
- **App stores** later for mobile monitoring.

### 15.3 B2B channels (Phase 3+)

- Land via **executive protection** (warm from P3 self-scanners), expand to **workforce exposure**.
- Security communities, CISO networks, design-partner program, then a small outbound + partnerships (MSSPs, identity vendors) motion. API developer marketing for P6.

### 15.4 Messaging

- B2C: *"See what the internet knows about you — then make it forget."* Calm, empowering, honest.
- B2B: *"Your people are your attack surface. Find and remove the exposure before attackers use it."*
- Throughout, lead with trust: how little we keep, consent-first, exclude-me-anytime. Our safety posture is marketing, not just compliance.

### 15.5 Launch sequence

Private beta (MVP cohort) → public free scan + waitlist conversion → paid Plus/Pro GA → family/depth → B2B design partners → API beta. Each launch is gated on the prior phase's metrics (§13.7, §18).

---

## 16. Pricing & packaging

### 16.1 Principles

Free where it builds trust and funnel (the scan); paid where there's ongoing work and value (monitoring + removal); priced *against proven incumbent willingness-to-pay* (DeleteMe ~$104–199/yr, Incogni ~$155/yr, Optery ~$48–300/yr) but justified by **doing more than brokers**. We never monetize by selling subject data — only the subject (or their authorized protector) pays.

### 16.2 B2C packaging

| Plan | Price (target) | What you get | Maps to |
|---|---|---|---|
| **Free Scan** | $0 | One-time self-scan, Exposure Score, full report, read-only hardening checklist | Funnel / P1 |
| **Plus** | ~$8–10/mo ($96–108/yr) | Everything in Free + continuous monitoring + alerts + re-scans + score trend | P1/P3 |
| **Pro** | ~$15–20/mo ($180–240/yr) | Plus + automated broker removal + DROP/DSAR + re-listing watch + priority + exports | P2 |
| **Family** | ~$25–35/mo | Pro for up to N members; guardian controls | P3 |

Rationale: Free Scan beats incumbents' paywalled discovery and drives PLG. Plus undercuts or matches broker-only services while covering *more categories*. Pro reaches Optery-Ultimate price but bundles removal **and** breach/social/records — a fuller job. Family captures the high-WTP exposed-by-role persona.

### 16.3 B2B packaging (Phase 3+)

| Plan | Model | What you get |
|---|---|---|
| **Team** | per monitored identity / mo (e.g., exec protection, ~$X/identity/mo) | T1/T2 monitoring, removal, alerts to Slack/email, basic dashboard |
| **Business** | seats + monitored identities, annual | + SSO, RBAC, audit export, SIEM/webhook, SLA |
| **Enterprise** | annual contract, custom | + workforce-scale, T3 vetted program, custom sources, dedicated support, DPA, SOC 2/ISO evidence |
| **API** | usage-based (per scan / tier) | Programmatic T0/T1 (later vetted T3); volume tiers; audit included |

B2B pricing is value-based (cost of a breach / exec incident ≫ subscription) and lands far higher ACV than B2C, which is the margin engine once the core is proven.

### 16.4 Packaging guardrails

- The **safety floor** (audit, exclude-me, delete-everything, rate limits) is in *every* tier including Free — never a paid upsell.
- Higher tiers buy *more automation and coverage*, never *fewer safeguards* or *looser rules*.
- T3 is never bundled or self-serve; it's an Enterprise add-on with contractual controls.

---

## 17. Business model & unit economics

### 17.1 Revenue streams

1. **B2C subscriptions** (Plus/Pro/Family) — the volume engine; recurring; expands via removal/monitoring.
2. **B2B subscriptions** (Team/Business/Enterprise) — high ACV; the margin engine from Phase 3.
3. **API usage** (Phase 4) — usage-based, developer/analyst demand.
4. *(Never)* data sales. Excluded by design and by the trust thesis.

### 17.2 Cost structure (what actually drives COGS)

| Cost | Driver | Control |
|---|---|---|
| **Third-party data APIs** | Per scan × sources × frequency — the dominant variable cost | Caching, diff-only re-scans, tier-aware concurrency, volume contracts, per-connector budget guards |
| Compute/storage | Scan jobs, vault, search index | Queue backpressure, short retention |
| Removal ops | Assisted/automated opt-outs, support | Automate brokers; deflect with self-serve |
| Trust & safety | Review queue, tooling, counsel | Automate detection; human-review only the flagged tail |
| Compliance | SOC 2/ISO, registrations, DPO | Phased; unlock enterprise revenue |

The existential margin risk is **data-API cost per active user outrunning ARPU**, especially on monitoring (repeated re-scans). Mitigations are first-class in architecture (§10.8): cache aggressively, re-scan by diff, and wire per-connector cost into COGS dashboards with hard budget guards. Target **blended gross margin 70%+ at B2C scale, 80%+ on B2B**, lower early while contracts are small.

### 17.3 Illustrative B2C unit economics (assumptions, to be validated)

> These are *modeling assumptions for planning*, not promises — every input is a hypothesis the MVP/Phase 1 will test.

- Blended paid ARPU ~$140/yr (mix of Plus/Pro/Family).
- Variable cost/paid user/yr (data + compute + removal) ~$35–45 → contribution margin ~$95–105/yr (~68–72%).
- Free→paid conversion 4–6%; paid gross monthly churn target < 2.5% (annual logo retention ~80%+; removal/monitoring are sticky because stopping = exposure returns).
- Blended CAC target < ~$40 via SEO/PLG/referral → **CAC payback < 6 months**, LTV:CAC > 3:1 once retention holds.

These are the levers the model lives or dies on; §18 instruments every one.

### 17.4 Illustrative trajectory (directional)

| Stage | Paid users | Notes |
|---|---|---|
| Beta (M3) | ~10² (founding/beta) | Validate aha + WTP |
| B2C GA (M9) | low thousands | PLG + SEO ramp; prove retention |
| Expansion (M18) | tens of thousands B2C + first B2B logos | Two engines running |
| Scale (M24) | path to $5–10M ARR run-rate | B2B ACV compounds B2C base |

### 17.5 Funding posture

A pre-seed/seed-shaped plan: MVP + Phase 1 on a small raise (build, prove aha + retention + early WTP), then raise on B2C traction to fund B2B/compliance (SOC 2, registrations) and the API. Capital-light early because the product sells itself; capital goes to data contracts, compliance, and the B2B motion later.

---

## 18. Metrics & KPIs

### 18.1 North Star

**Verified exposure reduced** — the cumulative drop in Exposure Score across active users (i.e., real exposure removed, not just detected). It aligns the company with the user's actual win and with retention (you stay because it keeps working).

### 18.2 Funnel (AARRR)

| Stage | Metric |
|---|---|
| Acquisition | Visitors → scans started; CAC by channel; SEO rankings on category terms |
| Activation | Scan completion %, report-viewed %, "learned something new" % |
| Revenue | Free→paid %, ARPU, tier mix, expansion (Plus→Pro→Family) |
| Retention | Gross/net revenue retention, monthly churn, score-improvement cohort retention |
| Referral | Invite/share rate, k-factor |

### 18.3 Product health

Findings precision/recall (sampled QA), entity-resolution accuracy (false-merge rate), scan latency, monitoring alert precision (low false-alarm), remediation success rate (opt-out → actually removed), re-listing rate, time-to-first-action.

### 18.4 Trust & safety metrics (reported, partly public — §9.8 FR-TS-5)

Scan-tier distribution, refusal/hold counts and reasons, abuse actions taken, exclude-me requests honored & median time, DSAR/deletion fulfillment time, audit coverage (must be 100%), security incidents (target 0). These are board-level metrics, not footnotes — a spike in non-self abuse signals or a miss on exclude-me is a company-health issue.

### 18.5 B2B metrics (Phase 3+)

ACV, logo & net revenue retention, identities monitored, exec incidents prevented (qualitative + customer-reported), API call volume & margin, time-to-value in pilots.

---

## 19. Legal, compliance & risk

> Not legal advice; a planning map. Engage privacy counsel before launch and before each new tier/source/jurisdiction. Compliance is a *feature set and an architecture*, not a disclaimer.

### 19.1 Regulatory map

| Regime | Applies to | Ayin's posture |
|---|---|---|
| **FCRA (US federal)** | Consumer reports for employment/credit/housing/insurance | **Hard non-goal.** No eligibility use; verify users + purpose; monitor for misuse; no character/eligibility scoring. Disclaimers alone are *not* a defense (FTC *Filiquarian*), so we build procedures. |
| **CCPA/CPRA + CA Delete Act / DROP** | CA residents' data; "data brokers" | Honor deletion/opt-out; register if we meet the broker definition; **integrate DROP** as a user feature; honor DROP against ourselves. |
| **State data-broker laws (CA/TX/OR/VT…)** | Businesses processing data on people with no direct relationship | Register where required; pay fees; maintain security program (VT); track the expanding state list. |
| **GDPR/UK GDPR** | EU/UK data subjects | Legitimate-interest basis + documented LIA/balancing; narrow "publicly available" test; full data-subject rights; DPA/processor terms for B2B; consider EU representative when serving EU. |
| **State privacy laws (VA/CO/CT/…)** | Residents' data | Honor access/deletion/opt-out; align to the strictest common denominator. |
| **Computer-misuse / ToS / anti-scraping** | Data acquisition method | Only "publicly available" per §11.1; respect ToS/robots; no auth bypass; counsel sign-off per connector. |
| **Defamation / accuracy** | Findings shown about a person | Source + confidence on every finding; no AI speculation; correction/dispute path. |

### 19.2 The "are we a data broker?" question

Likely **yes** under some state definitions (we process data about people we have no direct relationship with). We plan for it rather than hope to dodge it: register where required, run the required security program, and — critically — **avoid the *selling* the laws most target.** Ayin is paid by the subject/protector, minimizes retention, and offers exclusion. We aim to be the *anti*-broker that happens to fall under broker registration: same registry, opposite incentive. Counsel confirms classification per state pre-launch.

### 19.3 The FCRA bright line (most important legal control)

The single fastest way to become an accidental regulated entity is to let Ayin be used for hiring/tenant/credit/insurance decisions. Controls: explicit AUP prohibition; purpose attestation that screens these out; user verification; abuse monitoring for screening-like patterns (e.g., bulk scans of job applicants); no eligibility/character scoring in any report; rapid enforcement (suspend/ban) on detection. We would rather lose a customer than gain an FCRA classification.

### 19.4 Compliance roadmap

Pre-MVP: ToS/AUP, privacy policy, connector legal sign-offs, retention/deletion implemented, audit log live. Phase 1: DSAR/deletion ops, state registrations as triggered, DROP integration. Phase 3 (enterprise): SOC 2 Type II, ISO 27001, DPA program, pen tests, DPO/role. Ongoing: source re-reviews, transparency reports, regulatory monitoring.

### 19.5 Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Product misused for stalking/harassment** | Med | Critical (safety + reputation + legal) | T0-only MVP; KYC; purpose; rate/anomaly limits; refusal; audit; exclude-me; victim protections; fast bans (§20) |
| R2 | **Accidental FCRA/CRA classification** | Med | Critical | §19.3 controls; counsel; no eligibility scoring |
| R3 | **Classified a data broker w/ obligations** | High | Med | Plan to register; anti-selling structure; honor DROP |
| R4 | **Data-source ToS change / cutoff** | High | Med | Connector abstraction; multi-source; governance; legal review |
| R5 | **Inaccurate findings → defamation/harm** | Med | High | Source+confidence; QA harness; dispute path; no speculation |
| R6 | **Our own breach (we hold sensitive data)** | Med | Critical | Minimize retention; PII vault; crypto-shred; least-privilege; pen tests; incident plan; cyber insurance |
| R7 | **Data-API COGS > ARPU** | Med | High | Caching, diff re-scans, budget guards, volume contracts (§10.8, §17) |
| R8 | **Big-tech/incumbent enters** | Med | Med | Trust moat + remediation flywheel + two-sided engine |
| R9 | **Regulation tightens / bans third-party OSINT** | Med | Med-High | Self/consented core is durable; T3 is small & severable; build with rails not against |
| R10 | **Brand/PR incident ("creepy" perception)** | Med | High | Consent-first messaging, transparency reports, advocacy partnerships, visible exclude-me |

---

## 20. Trust, safety & ethics charter

This charter is a product spec, not a values poster. It binds what we build.

### 20.1 Prohibited uses (enforced, not just stated)

Stalking, harassment, intimate-partner surveillance; identifying/profiling **minors**; doxxing or facilitating it; **stranger facial recognition**; any **FCRA-covered eligibility** use (employment/tenant/credit/insurance); building third-party dossiers for sale; intimidation or targeting based on protected characteristics. Enforcement: detection heuristics + purpose checks + review queue → throttle, step-up, hold, suspend, ban; severe cases reported per legal obligation.

### 20.2 Protections for vulnerable & at-risk people

- **Anti-stalking design:** self-scan default; rate/cooldown limits on any non-self subject; anomaly detection tuned to stalking patterns (repeated scans of one person, clustering around an address); the riskiest tier (T3) is the hardest to access.
- **Victim safeguards:** priority "exclude me," expedited removal help, and partnerships with DV/anti-stalking orgs; we design so Ayin can *protect* P4 and can never become the *weapon* against P4.
- **Minors:** out of scope as subjects; age signals trigger refusal.

### 20.3 Transparency & accountability

Public AUP and "publicly available" definition; per-finding sourcing; periodic transparency report (volumes, refusals, abuse actions, exclusions honored); a visible, low-friction **exclude-me** flow; a dispute/correction path; internal access to subject data audited like any scan.

### 20.4 Data stewardship

Minimize collection and retention; keep findings/score, not permanent raw dossiers; encrypt and crypto-shred; real "delete everything"; never sell subject data. We are judged by how little we keep and how easily a person can make us forget them.

### 20.5 Decision rule for any new feature

> *"Is this feature more valuable to someone protecting themselves (or a party they're lawfully responsible for) than to someone targeting another person? Can we verify the requester, bound the purpose, rate-limit it, audit it, and let subjects exclude themselves?"* If not, it doesn't ship — or it ships only behind T3-grade gates. This rule is applied in design review and recorded.

---

## 21. Team & org to build it

| Phase | Core roles |
|---|---|
| **MVP** | Founder/PM; 2 backend (orchestration, connectors, ER); 1 frontend; 1 product designer (PT); fractional privacy counsel (source + ToS sign-off) |
| **B2C GA** | + 1 backend (remediation/monitoring), + growth/SEO, + support/removal-ops, + data partnerships (contracts) |
| **B2B / scale** | + security/compliance lead (SOC 2/ISO), + Trust & Safety lead + reviewers, + B2B sales/CS, + DPO/role, + ML for ER/scoring |

Culture note: hire a **Trust & Safety lead before, not after, opening third-party tiers.** In this category, T&S is product, and being late is how you become a cautionary tale.

---

## 22. Open questions, assumptions & decisions

### 22.1 Decisions made (recorded)

- **Scan model:** open OSINT with hard safeguards; **MVP is self-scan (T0) only.**
- **Wedge:** B2C free scan → paid monitoring/removal; B2B later on the same engine.
- **Non-goals locked:** no FCRA uses, no stranger facial recognition, no minors, no data selling, no real-time location, no auth-bypass acquisition.
- **Format/architecture:** scan-as-pipeline, swappable connectors, PII vault, audit-from-day-one.

### 22.2 Key assumptions to validate

- Free→paid ≥ 4–6% and paid retention strong enough for LTV:CAC > 3:1 (§17.3).
- Findings accuracy ≥ ~90% is achievable across breach + social + broker at MVP scope (§13.7).
- Data-API COGS stays well under ARPU with caching/diff re-scans (§10.8, §17.2).
- SEO/PLG can hold CAC < ~$40 in a competitive category.
- B2B exec-protection demand converts from B2C P3 users (§6, §15).

### 22.3 Open questions (need a decision)

1. **Primary launch geography** — US-first (DROP/Delete-Act tailwind, FCRA care) vs. include EU early (GDPR LIA work)? *Recommendation: US-first, EU in Phase 2.*
2. **Concierge pre-MVP?** Run 25–50 manual scans first to de-risk accuracy/WTP (§13.9)? *Recommendation: yes.*
3. **Breach data provider(s)** — primary + backup; commercial terms; display rules for credential exposure.
4. **Broker coverage depth at GA** — how many brokers before Pro is credible vs. category-completeness messaging.
5. **Score methodology governance** — who owns the rubric, how versioned, how we communicate score changes.
6. **T3 timing & vetting bar** — when (if) to open vetted third-party scans, and the KYC/contract standard.
7. **Pricing validation** — exact Plus/Pro/Family points vs. incumbents; annual vs. monthly default.
8. **Build vs. buy for entity resolution** at scale (rules → ML threshold).
9. **Insurance & entity structure** — cyber + E&O; corporate structure that reinforces "not a data seller."
10. **Mobile** — when monitoring/alerts justify native apps.

---

## 23. Appendices

### 23.1 Glossary

- **OSINT** — open-source intelligence: gathering from publicly available sources.
- **Exposure Score** — Ayin's 0–100 measure of a subject's public exposure/exploitability (not a person-score).
- **Tier (T0–T3)** — scan type by subject relationship: self / consented / protected-party / lawful third-party.
- **Data broker** — a business that collects and sells data on people it has no direct relationship with.
- **DROP** — California's Delete Request and Opt-out Platform (live Jan 1, 2026) for one-stop broker deletion.
- **DSAR** — Data Subject Access/Deletion Request (GDPR/CCPA-style).
- **Stealer log** — data harvested by info-stealing malware (credentials, sessions); an exposure source we *detect*, never purchase.
- **Entity resolution** — merging records that refer to the same person with confidence.
- **PII vault** — encrypted, access-controlled, short-retention store for sensitive subject data.

### 23.2 Exposure data taxonomy

| Category | Example findings | Default sensitivity |
|---|---|---|
| Credentials | breached password exposure, exposed email-in-breach, stealer-log mention | High–Critical |
| Identifiers | phone, address, DOB on broker listings | High |
| Social/public | public profiles, posts, photos the user published, bios | Low–Med |
| Records | property, voter, court, business filings (where public) | Med |
| Linkage | username→email→name correlations that de-anonymize | Med–High |
| Image/likeness (self) | where the user's own photo appears | Med |

### 23.3 Exposure Score rubric (v0 sketch)

- **Inputs:** findings weighted by *sensitivity* × *exploitability* × *recency* × *corroboration*, summed per category, normalized to 0–100, with category sub-scores.
- **Examples of weight:** live exposed credential ≫ broker listing ≫ public LinkedIn. A breached password reused across accounts scores far higher than a public bio.
- **Explainability:** each point traces to findings; "fix this → score drops by ~X."
- **Versioning:** data-driven changes (new finding) vs. methodology changes (rubric update) are labeled separately so trends stay honest.
- **Guardrail:** measures exposure only — never character, credit, or eligibility.

### 23.4 Sample report skeleton (what a user sees)

1. **Exposure Score** (hero) + one-line plain-language verdict.
2. **Top 3 things to fix now** (highest score impact × ease).
3. **By category** — Credentials / Identifiers / Social / Records / Linkage, each with findings (what, where, captured-when, source, confidence) and an action.
4. **Your remediation plan** — tracked tasks (manual in MVP; automated in Pro).
5. **Watch for changes** — monitoring upsell / status.
6. **Your data & rights** — what Ayin keeps, delete-everything, exclude-me.

### 23.5 Sources & references

Market sizing:

- [Personal Data Removal Services Market (DataIntelo)](https://dataintelo.com/report/personal-data-removal-services-market)
- [Open-Source Intelligence Market (GM Insights)](https://www.gminsights.com/industry-analysis/open-source-intelligence-osint-market)
- [OSINT Market (Verified Market Research)](https://www.verifiedmarketresearch.com/product/open-source-intelligence-osint-market/)

Competitor pricing & landscape:

- [Best Data Removal Services 2026 (Security.org)](https://www.security.org/data-removal/best/)
- [Optery vs DeleteMe vs Incogni (Cybernews)](https://cybernews.com/privacy-tools/optery-vs-deleteme-vs-incogni/)
- [Incogni: best data removal tools](https://blog.incogni.com/essential-data-removal-tools/)
- [15 Best OSINT tools (Lampyre)](https://lampyre.io/blog/15-best-osint-tools-in-2025/)

Breach data & sources:

- [Have I Been Pwned API v3](https://haveibeenpwned.com/api/v3)
- [Have I Been Pwned subscriptions](https://haveibeenpwned.com/Subscription)

Legal & compliance:

- [FTC: Background screening reports and the FCRA (disclaimers insufficient)](https://www.ftc.gov/business-guidance/blog/2013/01/background-screening-reports-fcra-just-saying-youre-not-consumer-reporting-agency-isnt-enough)
- [California DROP (privacy.ca.gov)](https://privacy.ca.gov/data-brokers/)
- [CPPA: Delete Act regulations approved](https://cppa.ca.gov/announcements/2025/20251113.html)
- [TechCrunch: Californians can demand brokers delete data (DROP)](https://techcrunch.com/2026/01/03/california-residents-can-use-new-tool-to-demand-brokers-delete-their-personal-data/)
- [GDPR Art. 6 — Lawfulness of processing](https://gdpr-info.eu/art-6-gdpr/)
- [Staying GDPR-compliant when using OSINT (Trustfull)](https://trustfull.com/articles/staying-gdpr-compliant-when-using-osint-for-fraud-prevention)
- [State data broker law comparison (CA Lawyers Assn.)](https://calawyers.org/privacy-law/data-broker-regulation-framework-a-comparative-analysis-of-california-texas-vermont-and-oregon/)

*Market figures are third-party estimates and vary by source; treat as directional, not precise.*

---

*End of document — Ayin PRD & SaaS Plan v0.1. Living document; update the version table on material change.*











