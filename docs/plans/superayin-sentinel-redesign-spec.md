# SuperAyin "Sentinel" redesign — build spec (2026-07-11)

Full-site visual redesign. Direction: **Sentinel — Trust & Authority** (bank-grade security
product: proof-forward, calm, credible). Replaces the 2026-06-21 "iris" design (Fraunces serif,
warm slate, cyan accent). New logo: **ʿAyin monogram** (the Hebrew letter ע — "ayin" means *eye*).

This file is the **shared contract** for all build workers. Deviate only where a rule below
conflicts with something factual in the codebase — then keep the code working and note it.

## Non-negotiables (from CLAUDE.md + PRD §12.1 — apply to design too)

1. **Calm, not alarmist.** Severity colors stay muted (critical = plum-rose, never fire-red).
   Words carry meaning; color only tints.
2. **No fabricated trust signals.** NO fake testimonials, customer logos, certification badges,
   invented stats, or star ratings. Real trust signals only: self-scan-only, sourced findings,
   audit log, delete-everything, exclude-me, short retention, no data selling. Reuse factual
   claims already in the current copy; do not invent numbers.
3. **Self-scan-only framing everywhere.** Never imply you can scan someone else.
4. **No emoji as icons** — inline SVG only (Lucide-style stroke icons, stroke-width 1.5–2, drawn
   inline; do NOT add icon package dependencies).
5. Accessibility: text contrast ≥ 4.5:1, visible focus states, 44px touch targets,
   `prefers-reduced-motion` respected (the global gate in globals.css stays).

## Design tokens (single source: `frontend/app/globals.css`)

Rewrite the `:root` values to Sentinel. **Keep every existing token NAME and every legacy alias
working** (`--bg --surface --border --text --text-dim --accent --ok --warn --down`, the
`--ink-*`, `--iris-*`, `--sev-*`, `--fs-*`, `--sp-*`, `--r-*`, `--e-*`, `--z-*`, `--dur-*`
families) — components read them; only values change. Add new `--cta-*` tokens.

### Dark (default)

| Token | Value | Note |
|---|---|---|
| `--ink-950` (new) | `#0A0F1E` | deepest band |
| `--ink-900` | `#0F172A` | page background |
| `--ink-800` | `#131D33` | raised section band |
| `--ink-700` | `#16213A` | card surface |
| `--ink-600` | `#1C2A47` | elevated / nested panel |
| `--ink-550` | `#20304F` | input fill, code well |
| `--line` | `#26345333`→ use solid `#263453` | hairline border |
| `--line-strong` | `#35476E` | focused edge |
| `--fg` | `#F1F5F9` | primary text |
| `--fg-dim` | `#97A6BC` | secondary (AA on ink-700/900) |
| `--fg-faint` / `--text-mute` | `#8494AC` | tertiary — keep ≥4.5:1 at small sizes |
| `--iris-400` | `#60A5FA` | links, focus, hover (trust blue) |
| `--iris-500` | `#3B82F6` | primary brand blue |
| `--iris-600` | `#2563EB` | pressed |
| `--iris-glow` | `rgba(59,130,246,0.22)` | focus ring / aura |
| `--indigo-500` | `#1D4ED8` | gradient end (deep blue — kept name) |
| `--on-iris` | `#051226` | ink on blue fills |
| `--cta-400` (new) | `#4ADE80` | CTA hover |
| `--cta-500` (new) | `#22C55E` | **conversion CTA fill — the ONLY green** |
| `--cta-600` (new) | `#16A34A` | CTA pressed |
| `--on-cta` (new) | `#04120A` | ink on CTA |
| `--sev-low` | `#57B896` | muted teal |
| `--sev-medium` | `#5E9EE6` | calm blue |
| `--sev-high` | `#D9A45B` | amber-clay |
| `--sev-critical` | `#C27D92` | plum-rose (calm) |
| sev `*-bg` | same hues at 10% alpha | |
| `--ok` | `#57B896` | |
| `--info` | `#5E9EE6` | |
| `--status-down` | `#D9806E` | infra only |

Elevation/z/motion/spacing/radii/type-scale token values stay as-is EXCEPT:
`--r-pill` stays for pills; **buttons move from pill to `--r-md` (12px)** — enterprise, not bubbly.

### Light variant (`:root[data-theme="light"]`) — keep the hook, retune values

bg `#F8FAFC` · band `#FFFFFF` · card `#FFFFFF` · elevated `#F1F5F9` · input `#EEF2F7` ·
line `#DEE5EF` / strong `#C3CEDE` · fg `#0F172A` · dim `#4A5A74` · faint `#66788F` ·
blue 400/500/600 `#2563EB`/`#1D4ED8`/`#1E40AF` · cta `#16A34A` (on-cta `#FFFFFF`) ·
sev low `#25836A` med `#2568B8` high `#A66A21` crit `#A14E6C`.

### Typography

- **All display + body: Plus Jakarta Sans** (`--font-jakarta`). **Mono: JetBrains Mono**
  (`--font-jetbrains`) for provenance facts, `.meta`, `.eyebrow`, code.
- `globals.css`: `--font-display: var(--font-jakarta), ...sans fallbacks` (no serif fallback),
  `--font-sans: var(--font-jakarta), ...`, `--font-mono: var(--font-jetbrains), ...`.
- Headings: weight 700 (hero 800), `letter-spacing: -0.025em`, `line-height: 1.08`.
- `layout.tsx` loads exactly: `Plus_Jakarta_Sans({ subsets:["latin"], display:"swap",
  variable:"--font-jakarta" })` and `JetBrains_Mono({ subsets:["latin"], display:"swap",
  variable:"--font-jetbrains" })` (both variable fonts — NO `weight` array), applied on `<html>`.
  Remove Fraunces/Inter/IBM Plex Mono.
- Type scale tokens unchanged; hero `--fs-display` may tighten to `clamp(2.5rem, 5.5vw, 4.25rem)`.

### Buttons (globals.css)

- `.btn` → `border-radius: var(--r-md)`; weight 650.
- `.btn-primary` → **CTA emerald**: `background: var(--cta-500); color: var(--on-cta);`
  hover `--cta-400` + subtle lift (`translateY(-1px)`, shadow); pressed `--cta-600`.
- `.btn-ghost` → unchanged contract (border `--line-strong`, hover `--ink-600`).
- NEW `.btn-blue` → `background: var(--iris-500); color: #fff;` hover `--iris-400`
  (secondary/product actions; conversion CTAs stay emerald).
- Focus rings stay blue (`--iris-400`).

## Logo — decision record (2026-07-11)

Four visual iteration rounds (18 geometry variants, judged at 140/48/32/16px, dark + light +
favicon tile + wordmark lockup). **Winner: V14 "the ʿayin glance"** — the ע's long arm sweeps
from upper-right through the baseline foot; the second arm is flattened into a lower lid; the
trust-blue pupil rests free in the counter. Chosen because it is the only candidate that reads
as an *eye* (calm, heavy-lidded glance) rather than a lowercase "y" (rounds 1) or a
cheering-person-with-ball-head (rounds 2–3, caused by symmetric raised arms + high dot).
Runner-up: V12 "asymmetric authentic" (best pure letterform; geometry banked in the session
scratchpad `logo.html` history). Final geometry (viewBox 0 0 48 48, stroke 3.6 round-cap):
- long arm + foot: `M40 12 C36 19 31 25 25.5 28.8 C20.5 32.5 15 35.4 9.5 36.2`
- lower lid: `M8 20 C12 24 17.5 27 24 28.9`
- pupil: `cx 26 cy 20.6 r 4.3`, radial `--iris-400 → --indigo-500`

## Logo — DO NOT TOUCH (worker rule during the build)

`components/IrisMark.tsx`, `app/icon.svg`, `app/opengraph-image.tsx` are being redesigned by the
orchestrator in parallel. Workers must NOT edit these three files. The component contract is
unchanged: `IrisMark({ size?, animate?, title?, decorative? })` default export — keep importing it
exactly as today. Brand text next to the mark: "Ayin", Plus Jakarta Sans 700, tracking -0.01em.

## Voice & copy

- Tone: measured, factual, second person. Short declaratives. No fear-mongering, no exclamation
  points, no "hacker" theatrics.
- Hero H1: **"Your exposure, measured."** Sub: keep the existing promise (see what the open
  internet knows about identifiers you control · Exposure Score 0–100 · a plan to shrink it ·
  self-scan only). Primary CTA: **"Run my free scan"**. Secondary: "How it works".
- The old slogan "See what the internet knows about you — then make it forget" survives as a
  supporting line (and stays in metadata/JSON-LD unchanged unless scoped below).

## Per-worker scopes (STRICT file boundaries — edit nothing outside your list)

### W1 — tokens + utility layer: `frontend/app/globals.css` ONLY
Apply the token tables above. Keep ALL existing class names working (`.card .btn .pill .field
.site-header .nav-* .trail .sticky-cta .eyebrow .lead .meta .sev-* .dot .dim` etc. — components
depend on them). Restyle, don't rename. Keep the reduced-motion gate, skip-link, aliases block,
light-theme block (retuned), `.iris--focus` keyframes (logo animation hooks — keep class names;
values may be tuned). Buttons per spec. Add `.btn-blue`, `--cta-*`, `--ink-950`, and a
`.trust-bar` utility (flex row of small mono guarantees separated by hairlines, wraps on mobile).

### W2 — fonts + shell: `frontend/app/layout.tsx`, `frontend/app/manifest.ts`
Fonts per Typography (exact variable names `--font-jakarta`, `--font-jetbrains`). Update
`viewport.themeColor` to `#0F172A`. Metadata/JSON-LD text content: keep as-is (SEO-locked) —
only mechanical changes needed for fonts. manifest.ts: `background_color`/`theme_color` →
`#0F172A`; keep name/short_name/icons contract intact.

### W3 — chrome: `frontend/components/Header.tsx`, `frontend/components/Footer.tsx`
Rebuild both in Sentinel. Header: sticky, blur, 64px, brand (IrisMark + "Ayin"), nav links
(keep every existing route link + auth-aware logic exactly as it behaves today), CTA button
`.btn-primary` (emerald) "Run my free scan" → existing target. Keep mobile `<details>` sheet
pattern + all a11y. Footer: restructure into a proof-forward footer — brand + one-line promise,
link columns (keep every existing link incl. /terms, /exclude, /status, mailto), and a
"safety floor" strip (self-scan only · sourced findings · delete everything · audit log) in
`.meta` mono. No new routes.

### W4 — landing: `frontend/app/page.tsx`, `frontend/components/LandingEnhancements.tsx`
Rebuild the marketing page in Sentinel, Trust & Authority structure:
1. **Hero** — eyebrow (mono, "PRIVACY SELF-SCAN"), H1 "Your exposure, measured.", lead, CTA pair
   (emerald primary + ghost "How it works"), `.trust-bar` (Self-scan only · Sources cited ·
   Delete everything · Free), right column: product-true score card (reuse ScoreRing component
   if it's already imported today; keep any demo data honest).
2. **Proof band** (`.section--band`) — REAL guarantees as stat-style cards (e.g. "0–100 scored
   exposure", "every finding sourced", "self-scan only by design"). No invented metrics.
3. **How it works** — 3 steps (verify it's yours → we scan public sources → you get a plan),
   reuse `.trail` visual language.
4. **What we find** — findings-category grid (breaches, broker listings, public footprint,
   username reuse) with calm sev accents; word-led pills.
5. **The score** — explain Exposure Score bands, calm framing.
6. **The safety floor / "What we never do"** — the differentiator section: no scanning others,
   no selling data, no dossiers, exclude-me, crypto-shred delete, audit from first scan.
7. **FAQ** — keep ALL existing FAQ Q/A text and the FAQPage JSON-LD **byte-equivalent in
   content** (structure may re-render; questions/answers must not change).
8. **Final CTA** — emerald.
Preserve: page-level `metadata` (title/description/canonical) unchanged; `#main-content` flow;
`main.landing`; all `id` anchors that exist today (e.g. `#how-it-works` if present — check);
`[data-reveal]` scroll-reveal + sticky mobile CTA behaviors via LandingEnhancements (keep its
exported contract; retune internals). All section content must remain truthful to the product.

### W5 — app surfaces: `frontend/components/{ScoreRing, ScorePanel, FindingsList,
HardeningChecklist, NarrativePanel, PlannerTrail, ScanPanel, IdentifierManager, DataRights,
ConsentManager, GettingStarted, IntentCTA, ScanPreview, StepUpModal, TosGate}.tsx`,
`frontend/app/dashboard/page.tsx`, `frontend/app/report/[scanId]/page.tsx`
Most styling flows from tokens automatically. Your job: sweep for hardcoded hex/rgb colors,
serif/`--font-display` assumptions, pill-radius buttons, and old-brand cyan references; align to
Sentinel (blue = interactive, emerald = the single primary action per screen, calm sev scale
untouched in semantics). Keep every component's props/exports/behavior identical (ScoreRing still
exports `bandColor`). Keep calm-gate rules: sev word-pills + 10px dots, mono provenance `.meta`.
No layout rewrites unless a surface visibly clashes with the new system — surgical restyle.

### W6 — aux pages: `frontend/components/AuthForm.tsx`, `frontend/app/{login, signup, exclude,
exclude/confirm, terms, status, consent, consent/revoke, verify-email, verify-identifier}/page.tsx`
Same surgical restyle rules as W5. Auth screens get the Sentinel treatment (card on `--ink-800`
band, emerald submit, blue links). Keep all copy, all metadata exports, all noindex layouts
untouched, all form behavior identical. The consent pages keep their anti-phishing notice and
all safety copy verbatim.

## Verification (orchestrator-run — workers do NOT run servers or builds)

Workers: edit files only. No `npm run build`, no dev servers, no `tsc` (the orchestrator runs the
full gate: tsc → next build → seo-assert (41 checks) → visual preview at 375/768/1280 + dark
default). Return a summary: files touched, decisions taken, anything you flagged.
