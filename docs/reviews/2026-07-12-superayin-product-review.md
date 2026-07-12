# SuperAyin product review — 2026-07-12

**Scope:** the current `main` build (Sentinel redesign, df513d6) reviewed across six dimensions —
usability, visual design, accessibility, workability/engineering health, copy/conversion, and
competitive standout. Evidence: live dev rig (demo backend + real scan with Qwen narrative),
full-page captures at 1440px/375px/dark/light of every public and authed surface, plus the
deployed (older) superayin.com build for contrast. Method: 6 reviewer agents → adversarial
verification of every objective finding (1–2 independent skeptics each) → completeness critic.
46 agents total; 4 findings were refuted and discarded.

**Status: every fix marked ✅ below was implemented and verified on 2026-07-12**
(tsc clean · `next build` clean, 20 routes · seo-assert 41/41 · no horizontal overflow at 375px ·
full visual pass at 1440/375, dark/light). Items marked ◻ are recommendations left open.

---

## The headline verdict

The product is **functionally strong and constraint-compliant** (calm palette held, no fabricated
trust signals, AA contrast verified by actual math), but as shipped it **did not stand out**: its
two genuinely novel assets — the hard self-scan-only trust gate and the auditable agentic scan
trail — were invisible on the marketing surface, while the hero led with 2026 table stakes (free
score, sourced findings). Visually it read as competent-but-generic dark SaaS: one card style for
everything, no depth outside the score rings, and an app shell that rendered as a 760px mobile
column on desktop.

### Competitive read (researched against the 2026 market)

- **Table stakes now:** free scan, sourced findings, encrypted short retention (HIBP, Mozilla
  Monitor, Incogni, Optery, DeleteMe all have versions of these). Mozilla shut down Monitor Plus
  removal in Dec 2025; Google "Results about you" expanded Feb 2026.
- **Genuinely novel to Ayin:** (1) architecturally *cannot* scan a third party — every competitor
  will happily scan someone else; (2) the agent's own reasoning trail (PlannerTrail) with source
  citations and AI attribution — no incumbent shows its work; (3) safety floor free at T0.
- **Winnable axis:** "the only exposure scanner that shows you its own work." For a Qwen-judged
  hackathon this is also exactly the AI story the judges need to see without logging in.

---

## What was fixed in this pass

### Differentiation / landing
- ✅ **New landing section "Every scan explains itself"** — a real AGENT ACTIVITY trail (mirrors
  the live PlannerTrail steps, incl. "Report written by Qwen · citation guard enforced") now sits
  on the marketing page; the AI story no longer requires three clicks + auth.
- ✅ **Proof band reordered and rewritten** to lead with self-scan-only + "Shows its work";
  rendered as a hairline-divided guarantee row instead of three more cards.
- ✅ **Hero right column rebuilt** — the lone floating ring became a "sample readout" product
  panel (ring + per-category bars + mono caption), giving the hero real product proof.

### Visual system
- ✅ **Atmospheric hero floor** — one deliberate radial-gradient moment (trust-blue/indigo, on
  the previously dead `--indigo-500` family); everything else stays flat by design.
- ✅ **Section bands** got hairline top/bottom edges; **NEVER cards** became outlined "refusal"
  chrome (`card--never`) so refusals and features no longer share a voice; **Qwen narrative card**
  got the escalated `card--glow` treatment (it's the signature surface).
- ✅ **Trust-bar bug** — separator CSS targeted `span` but markup is `<li>`: real bullets were
  colliding with hero text. Fixed selector + list reset (hero + footer both benefit).
- ✅ **Wordmark lockup** tightened (700 weight, -0.02em, line-height 1).
- ✅ **FAQ disclosure** marker now rotates + → × on open; summary is a 44px target.

### Logo
- ✅ **Full redesign — "the audited iris"** (see
  `docs/plans/superayin-audited-iris-redesign-spec.md` for the 4-round decision record). Calm
  almond glance; the iris is the product's own Exposure-Score gauge ring; collapses to a solid
  pupil below 24px. Same `IrisMark` contract; favicon + OG card updated in sync.

### Usability / correctness
- ✅ **Checklist stall** — "Building your personalized plan…" could hang forever on one swallowed
  fetch error. Now: 2 retries with backoff → explicit "Couldn't build your plan — Retry" state;
  loading copy sets expectations ("can take a minute or two"); `aria-live` announced.
- ✅ **Dead "Fix this →" CTA** on the dashboard (no remediation anchor exists there) — now
  navigates to `/report/{id}#fix-{finding}` via a new `reportHref` prop, or hides when no target.
- ✅ **Session expiry mid-flow** — shared 401 handler in `api()` redirects to
  `/login?next=…` (auth endpoints and login/signup pages exempt; page-level handlers unchanged).
- ✅ **NarrativePanel** no longer renders *nothing* on first-load failure (contradicted its own
  "fail soft, never blank" comment) — calm inline notice instead.
- ✅ **Re-scan double-fire guard** — button disabled while a scan is active or the request is in flight.
- ✅ **Raw connector IDs** ("fake: done (3)") replaced with human labels ("Demo source (synthetic
  fixtures)") via a display map with fallback.
- ✅ **App shell width** — dashboard/report moved from the 760px reading column to a 960px app
  measure, and the report's score panel + Qwen narrative now sit side-by-side ≥1024px.

### Accessibility (WCAG 2.2 AA)
- ✅ Form errors announced (`role="alert"` + `aria-describedby`) on AuthForm and StepUpModal.
- ✅ Async state announced (`role="status"` / `aria-live="polite"`) on scan progress, checklist
  build, verify-email/verify-identifier transitions.
- ✅ StepUpModal: real focus trap (capture → cycle → restore) — it declared `aria-modal` without
  trapping focus.
- ✅ `autocomplete` on all auth inputs (email / new-password / current-password).
- ✅ Touch targets — "Fix this →", Yes/No review buttons, "How to remove this", "Show the standard
  steps" raised to 44px min-height (they were 13–23px).
- ✅ Emoji glyphs (🔒/⚠) replaced with inline SVGs per the project's own no-emoji-icons rule.
- Verified as already-correct (no action): token contrast pairs all ≥4.5:1 dark AND light (checked
  numerically), native `<details>` FAQ semantics, ScoreRing/IrisMark SVG labeling,
  `prefers-reduced-motion` global gate.

### Copy / trust integrity
- ✅ **Absolute-claim durability** — "no lookup path for anyone else *exists*" (NEVER card + FAQ)
  contradicted the consent-gated T1 surface that already lives on `main` behind a flag. Rewritten
  to the enforcement truth ("refused at the gate and audited") which stays true before and after
  any flag flip. The FCRA line and self-scan wedge claim are untouched.
- ✅ `/status` page — was `force-dynamic` with zero caching, so any transient Redis blip was
  instantly visible to judges via the footer link. Now ISR (30s revalidate), calm
  "Operational / Needs attention" wording, real "last checked" timestamp, no invented uptime.
- ✅ verify-email success copy completed ("Your email is verified. Head to your dashboard…").

---

## Refuted findings (checked and discarded — do not re-fix)
- "Light theme is unreachable dead code" — it's a **documented, intentional** hook for the OG
  image route (globals.css comment); not a bug, no toggle wanted.
- "Light-mode `--fg-faint` sits at the AA floor" — moot for users (theme not user-reachable).
- "Score-band copy drifts from the engine" — verified consistent (30/55/80 in page.tsx,
  ScoreRing.bandColor, scoring engine).
- "Signup requires two email round-trips before a score" — false; the account email verification
  already counts as a verified anchor, so it's exactly one round-trip.

## Open recommendations (deliberate product calls — not made unilaterally)
- ◻ **Dashboard duplicates the report** (score ring, findings, possible-matches render on both).
  Root cause of the dead-CTA bug; also blurs which page is "the report". For the judged demo the
  single-page dashboard tour is arguably an asset — decide after the hackathon: trim ScanPanel to
  status + "View report" and let `/report` own results.
- ◻ Landing could tease the monitoring/removal business ("Watch for changes" exists only on the
  report today).
- ◻ PlannerTrail's "(no reasoning given)" line for the fake connector reads slightly unfinished in
  the judged demo — cosmetic backend copy.
- ◻ Consider a `next` param on login CTAs from deep pages (the 401 redirect now supplies it; the
  header "Sign in" does not).

## Deploy note
Everything above is committed to `main` but **NOT deployed** — superayin.com still serves the
June-21 build, and the deploy freeze during hackathon judging was respected. When you choose to
deploy, the standard push-to-main → ECS Send-Command recreate-web flow applies, and seo-assert
should be re-run against prod.
