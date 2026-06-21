# SuperAyin.com — THE BUILD SPEC

**Single source of truth for the redesign + SEO of superayin.com.** Base direction: **bold-conversion-product**, with grafts from the other three directions and the judges' notes. Stack is unchanged: Next 15 App Router, React 19, plain CSS in `app/globals.css` + inline-style objects, `next/font`. Dark stays the runtime default. **The token layer keeps every legacy variable name as an alias, so the existing login→scan→report demo cannot break from the token swap.**

> Absolute paths used throughout. Repo root: `C:\Users\Ong Jun Kai\OneDrive\Documents\Claude\Projects\Ayin`.

---

## 1. Final design language (locked, 3 sentences)

1. **Ayin means *eye*; the entire site dramatizes one reversal — you are the one holding the lens, never the one being watched** — expressed by a single calm signature motion (an iris that *focuses*, never a scanner that *hunts*) that is simultaneously the logo, the hero artifact, and the real ScorePanel ring.
2. **Boldness lives in scale and humane editorial type, never in urgency or color** — oversized Fraunces headlines and generous space carry confidence, while every "alarm" hue is pulled off pure red toward terracotta/amber/teal so a frightened person (the stalking-survivor persona) never meets a wall of red.
3. **Trust is shown, not claimed** — provenance facts render in monospace, severity is always carried by a *word* before a color, every finding leads with its fix, and the safety controls (exclude-me, delete-everything, audit) are promoted to hero features rather than buried in fine print.

**Two governing review gates (enforce in code review):**
- **Sensitivity-containment rule (from privacy-tech-dark, verbatim):** a sensitivity color may tint only a **10px dot**, a **1px edge**, or a **≤10%-alpha well** — NEVER a whole card or row background.
- **Word-before-color rule (from warm-human, satisfies WCAG 1.4.1):** every severity indicator is accompanied by an explicit word — `Low / Medium / High / Sensitive` — color is only a supporting cue.

---

## 2. Locked design tokens

Replace the entire `:root` block in `frontend/app/globals.css` with the following. **Paste-artifact fixes already applied** (single clean `--sev-high`, clean `--text-mute`). Legacy names (`--bg --surface --border --text --text-dim --accent --ok --warn --down`) are preserved as aliases at the bottom so no component changes are required for the swap.

```css
/* ============================================================
   AYIN DESIGN TOKENS — dark default. Calm, not alarmist (§12.1).
   Legacy var names kept as ALIASES at the bottom — do not remove.
   ============================================================ */
:root {
  /* ---- Ink stack (surfaces) — warm slate-navy, calmer than clinical grey ---- */
  --ink-900: #0b0e14;   /* page background */
  --ink-800: #11151d;   /* raised section band */
  --ink-700: #161b25;   /* card surface (== legacy --surface) */
  --ink-600: #1d2430;   /* elevated card / nested panel */
  --ink-550: #232b38;   /* input fill, code well */
  --line:        #28303d;   /* hairline border */
  --line-strong: #364150;   /* focused input, active card edge */

  /* ---- Text ---- */
  --fg:       #eef2f7;  /* primary */
  --fg-dim:   #9aa6b6;  /* secondary (AA on ink-700/900) */
  --fg-faint: #6b7689;  /* tertiary / captions (>= --fs-xs only) */
  --text-mute: #6b7689; /* alias spelling some grafts reference */

  /* ---- Brand: the iris. Cyan lens-light → indigo. ---- */
  --iris-400:  #6fd2ff;  /* bright accent: links, focus, hover */
  --iris-500:  #3ba9f0;  /* primary brand: CTA fill */
  --iris-600:  #2b7fd4;  /* pressed */
  --iris-glow: rgba(111, 210, 255, 0.20); /* focus ring + hero aura */
  --indigo-500:#7c6cff;  /* secondary brand / gradient end */

  /* ---- Sensitivity scale — CALM. Maps 1:1 to FindingsList tiers &
         ScorePanel bands. Critical = terracotta, never fire-red.
         Critical leans plum-rose (grave, "serious and handled"). ---- */
  --sev-low:      #5fb89a;  /* muted teal — minor / handled */
  --sev-medium:   #5aa9e6;  /* brand blue — worth knowing (NOT alarm-yellow) */
  --sev-high:     #e0a55a;  /* warm amber-clay — take a look */
  --sev-critical: #c77d8f;  /* muted plum-rose — do this first (earth-tone, de-risked) */
  --sev-low-bg:      rgba(95, 184, 154, 0.10);
  --sev-medium-bg:   rgba(90, 169, 230, 0.10);
  --sev-high-bg:     rgba(224, 165, 90, 0.10);
  --sev-critical-bg: rgba(199, 125, 143, 0.10);

  /* ---- Functional / status (operational, distinct from findings) ---- */
  --ok:   #5fb89a;   /* a quiet footprint is a good result */
  --info: #5aa9e6;
  --status-down: #df7d6e;  /* infra-down only; never a finding color */

  /* ---- Typography (families injected by next/font in layout.tsx) ---- */
  --font-display: var(--font-fraunces), Georgia, "Times New Roman", serif;
  --font-sans:    var(--font-inter), ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono:    var(--font-plex-mono), ui-monospace, "SF Mono", "Cascadia Code", monospace;

  /* Fluid type scale (1.25). Headings = display; body/UI = sans; facts = mono. */
  --fs-display: clamp(2.75rem, 6vw, 5rem);     /* hero H1 — Fraunces 540 / 1.02 */
  --fs-h1:      clamp(2rem, 4vw, 3rem);        /* section titles — Fraunces 520 / 1.08 */
  --fs-h2:      clamp(1.5rem, 2.5vw, 2rem);    /* sub-sections — Fraunces 500 / 1.15 */
  --fs-h3:      1.15rem;                        /* card titles — Inter 650 / 1.3 */
  --fs-lead:    clamp(1.05rem, 1.6vw, 1.35rem);/* hero subcopy / leads — Inter 420 / 1.55 */
  --fs-body:    1rem;                           /* body — Inter 420 / 1.6 */
  --fs-sm:      0.85rem;                        /* metadata — Inter 440 / 1.5 */
  --fs-xs:      0.72rem;                        /* pills, captions, citations — Inter 560 / 1.4 */
  --fs-score:   clamp(3rem, 7vw, 5.5rem);      /* Exposure Score numeral — mono/Inter 800, tnum */

  /* ---- Spacing (4px base) ---- */
  --sp-1:4px;  --sp-2:8px;  --sp-3:12px; --sp-4:16px; --sp-5:24px;
  --sp-6:32px; --sp-7:48px; --sp-8:64px; --sp-9:96px; --sp-10:128px;

  /* ---- Layout widths ---- */
  --mw-wide: 1120px;  /* marketing sections */
  --mw-read: 760px;   /* app / report column (was 720) */
  --gutter:  clamp(20px, 5vw, 64px);

  /* ---- Radii ---- */
  --r-sm:8px; --r-md:12px; --r-lg:18px; --r-xl:28px; --r-pill:999px;

  /* ---- Elevation (dark-tuned: hairline + soft ambient, no heavy drop) ---- */
  --e-0: none;
  --e-1: 0 1px 2px rgba(0,0,0,0.40), 0 0 0 1px var(--line);              /* resting card */
  --e-2: 0 8px 24px -8px rgba(0,0,0,0.60), 0 0 0 1px var(--line);        /* hover / raised */
  --e-3: 0 24px 64px -16px rgba(0,0,0,0.75), 0 0 0 1px var(--line-strong);/* hero / modal */
  --glow-iris: 0 0 0 3px var(--iris-glow);                               /* focus ring */
  --glow-aura: 0 0 40px -6px var(--iris-glow);                           /* iris mark / primary CTA */

  /* ---- Z-index scale ---- */
  --z-base: 0; --z-sticky-cta: 40; --z-header: 50; --z-overlay: 80; --z-modal: 100; --z-toast: 120;

  /* ---- Motion ---- */
  --dur-1:120ms; --dur-2:200ms; --dur-3:360ms; --dur-4:680ms; /* dur-4 = iris focus / count-up */
  --ease-out:    cubic-bezier(.2,.7,.2,1);    /* default UI */
  --ease-spring: cubic-bezier(.34,1.3,.5,1);  /* CTA press, score overshoot */
  --ease-iris:   cubic-bezier(.16,.84,.24,1); /* the focus settle */

  /* ============ BACK-COMPAT ALIASES — DO NOT REMOVE ============ */
  --bg:        var(--ink-900);
  --surface:   var(--ink-700);
  --border:    var(--line);
  --text:      var(--fg);
  --text-dim:  var(--fg-dim);
  --accent:    var(--iris-400);
  --warn:      var(--sev-high);
  --down:      var(--sev-critical);
}

/* Optional LIGHT variant — used ONLY by the OG image route + a deferred,
   non-default [data-theme=light] hook. NOT the runtime default. */
:root[data-theme="light"] {
  --ink-900:#f6f8fb; --ink-800:#ffffff; --ink-700:#ffffff; --ink-600:#f1f4f9; --ink-550:#eef2f8;
  --line:#e2e8f1; --line-strong:#cbd5e3;
  --fg:#0e1722; --fg-dim:#51607a; --fg-faint:#8694ab; --text-mute:#8694ab;
  --iris-400:#2b8fe0; --iris-500:#1f7fd1; --iris-600:#155fa6;
  --sev-low:#2f8f72; --sev-medium:#2f7fc4; --sev-high:#b5772a; --sev-critical:#a85070;
  --ok:#2f8f72; --status-down:#c25a48;
}

/* ---- Global reduced-motion gate (decorative motion off) ---- */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }
  [data-reveal] { opacity: 1 !important; transform: none !important; }
}
```

**Notes**
- The existing inline `transition: width 0.4s` on the ScorePanel bar is automatically neutralized by the reduced-motion block; no JS needed.
- `--down` aliases to `--sev-critical` (plum-rose), so `ScorePanel.bandColor` and `FindingsList.SENSITIVITY_COLOR` (which already read these vars) get the calm palette for free.
- `--fg-dim #9aa6b6` on `--ink-700 #161b25` ≈ 6.0:1, on `--ink-900 #0b0e14` ≈ 7.4:1 — passes AA. `--fg-faint`/`--text-mute` is for `≥ --fs-xs` non-essential captions only.

---

## 3. Reusable CSS / component primitives

Add the following utility layer to `frontend/app/globals.css` **after** the `:root` block. Keep `html, body, main, a, .card, .dot, .dim, code` (legacy) and extend. These classes let every page inherit the look; components may keep their inline-style objects, but new markup should prefer these.

```css
/* ---- Base ---- */
html, body { margin:0; padding:0; background:var(--bg); color:var(--fg);
  font-family:var(--font-sans); font-size:var(--fs-body); line-height:1.6;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }
body { font-feature-settings:"cv05" 1, "tnum" 1; }
h1,h2,h3,h4 { font-family:var(--font-display); letter-spacing:-0.015em; line-height:1.1; margin:0 0 var(--sp-4); }
h3 { font-family:var(--font-sans); font-weight:650; font-size:var(--fs-h3); letter-spacing:-0.005em; }
a { color:var(--iris-400); text-decoration:none; }
a:hover { text-decoration:underline; }
:focus-visible { outline:none; box-shadow:var(--glow-iris); border-radius:var(--r-sm); }

/* ---- Layout: containers + section rhythm ---- */
.container { max-width:var(--mw-wide); margin:0 auto; padding-inline:var(--gutter); }
.container-read { max-width:var(--mw-read); margin:0 auto; padding-inline:var(--gutter); }
main { max-width:var(--mw-read); margin:0 auto; padding:var(--sp-8) var(--gutter); } /* legacy app pages */
.section { padding-block:var(--sp-9); }
@media (max-width:720px){ .section { padding-block:var(--sp-7); } }
.section--band { background:var(--ink-800); }
.eyebrow { font-family:var(--font-mono); font-size:var(--fs-xs); letter-spacing:.12em;
  text-transform:uppercase; color:var(--fg-faint); margin:0 0 var(--sp-3); }
.lead { font-size:var(--fs-lead); color:var(--fg-dim); line-height:1.55; max-width:60ch; }

/* ---- Cards ---- */
.card { background:var(--ink-700); border:1px solid var(--line); border-radius:var(--r-md);
  padding:var(--sp-5); box-shadow:var(--e-1); margin-top:var(--sp-5); }
.card--raised { box-shadow:var(--e-2); }
.card--glow   { box-shadow:var(--e-1), var(--glow-aura); border-color:var(--line-strong); } /* SAFETY bento only */
.grid { display:grid; gap:var(--sp-5); }
.grid-3 { grid-template-columns:repeat(3,1fr); }
.grid-2 { grid-template-columns:repeat(2,1fr); }
@media (max-width:860px){ .grid-3,.grid-2 { grid-template-columns:1fr; } }

/* ---- Buttons ---- */
.btn { display:inline-flex; align-items:center; gap:var(--sp-2); min-height:44px;
  padding:0 var(--sp-5); border-radius:var(--r-pill); border:1px solid transparent;
  font:inherit; font-weight:600; cursor:pointer; transition:transform var(--dur-1) var(--ease-out),
  background var(--dur-1), box-shadow var(--dur-1); text-decoration:none; }
.btn:active { transform:translateY(1px) scale(.99); }
.btn-primary { background:var(--iris-500); color:#04121d; }
.btn-primary:hover { background:var(--iris-400); box-shadow:var(--glow-aura); text-decoration:none; }
.btn-ghost { background:transparent; color:var(--fg); border-color:var(--line-strong); }
.btn-ghost:hover { background:var(--ink-600); text-decoration:none; }
.btn-lg { min-height:52px; padding:0 var(--sp-6); font-size:1.05rem; }

/* ---- Pills / badges ---- */
.pill { display:inline-flex; align-items:center; gap:var(--sp-2); padding:2px 10px;
  border-radius:var(--r-pill); font-size:var(--fs-xs); font-weight:600; line-height:1.6;
  border:1px solid var(--line); color:var(--fg-dim); }
.pill-iris { color:var(--iris-400); border-color:color-mix(in srgb,var(--iris-400) 40%,transparent);
  background:var(--sev-medium-bg); }
/* severity pills: WORD carries meaning; color only tints a 1px edge + ≤10% well */
.sev-dot { width:10px; height:10px; border-radius:50%; display:inline-block; flex:none; }
.sev-low      { color:var(--sev-low); }
.sev-medium   { color:var(--sev-medium); }
.sev-high     { color:var(--sev-high); }
.sev-critical { color:var(--sev-critical); }

/* ---- Monospace truth texture (provenance facts) ---- */
.meta { font-family:var(--font-mono); font-size:var(--fs-xs); color:var(--fg-dim);
  letter-spacing:0; }

/* ---- Inputs / fields ---- */
.field { display:flex; flex-direction:column; gap:var(--sp-2); margin-bottom:var(--sp-4); }
.field label { font-size:var(--fs-xs); color:var(--fg-dim); text-transform:uppercase; letter-spacing:.06em; }
.field input, .field select { min-height:44px; background:var(--ink-550); color:var(--fg);
  border:1px solid var(--line); border-radius:var(--r-md); padding:0 var(--sp-4); font:inherit; }
.field input:focus { border-color:var(--line-strong); box-shadow:var(--glow-iris); outline:none; }

/* ---- Nav / header ---- */
.site-header { position:sticky; top:0; z-index:var(--z-header); height:64px;
  display:flex; align-items:center; backdrop-filter:blur(12px);
  background:color-mix(in srgb, var(--ink-900) 78%, transparent); border-bottom:1px solid transparent; }
.site-header.scrolled { border-bottom-color:var(--line); }
.nav-links { display:flex; gap:var(--sp-5); align-items:center; }
@media (max-width:760px){ .nav-links { display:none; } } /* mobile uses <details> sheet */

/* ---- Step trail (shared by landing how-it-works AND in-app PlannerTrail) ---- */
.trail { display:grid; gap:var(--sp-5); }
.trail-node { position:relative; padding-left:var(--sp-6); }
.trail-node::before { content:""; position:absolute; left:6px; top:6px; width:10px; height:10px;
  border-radius:50%; background:var(--iris-500); box-shadow:var(--glow-aura); }
.trail-node:not(:last-child)::after { content:""; position:absolute; left:10px; top:18px; bottom:-18px;
  width:1px; background:var(--line); }

/* ---- Scroll reveal (JS adds [data-reveal]; safe no-op without JS) ---- */
[data-reveal] { opacity:1; } /* default visible — progressive enhancement */
.js [data-reveal] { opacity:0; transform:translateY(16px); transition:opacity var(--dur-3) var(--ease-out), transform var(--dur-3) var(--ease-out); }
.js [data-reveal].in { opacity:1; transform:none; }

/* ---- Sticky mobile CTA bar (appears after hero scrolls out) ---- */
.sticky-cta { position:fixed; left:0; right:0; bottom:0; z-index:var(--z-sticky-cta);
  display:none; padding:var(--sp-3) var(--gutter); background:color-mix(in srgb,var(--ink-900) 92%,transparent);
  backdrop-filter:blur(12px); border-top:1px solid var(--line); }
@media (max-width:760px){ .sticky-cta.show { display:block; } }
```

**Primitive summary for the engineer:** `.container`/`.container-read` (widths) · `.section`/`.section--band` (rhythm) · `.card`/`.card--raised`/`.card--glow` · `.btn`/`.btn-primary`/`.btn-ghost`/`.btn-lg` · `.pill`/`.pill-iris`/`.sev-*`/`.sev-dot` · `.meta` (mono provenance) · `.field` · `.site-header`/`.nav-links` · `.trail`/`.trail-node` · `[data-reveal]` · `.sticky-cta`.

---

## 4. Landing page — final section-by-section spec

Replace `frontend/app/page.tsx`. **Remove `export const dynamic = "force-dynamic"` and the `fetchHealth()` call** → add `export const dynamic = "force-static"`. The page must render with the API down (the system-status widget moves to a new `/status` route, §6/§8). One `<h1>`. Sections wrapped in `<section aria-labelledby="...">`. Copy below is FINAL.

**Order:** Header → Hero → Asymmetry-flip band → Trust strip → How it works → The agent (Qwen) → Before/After → Safety & control → Differentiator → FAQ → Final CTA → Footer → Sticky mobile CTA.

### S1 — Hero
- Markup: two-column inside `.container` (copy ~55% left, iris SVG right; stacks on mobile, iris below).
- **Eyebrow (mono):** `OSINT SELF-EXPOSURE SCANNER · QWEN AI HACKATHON · TRACK 4`
- **H1 (Fraunces, `--fs-display`):** `See what the internet knows about you.`
- **H1 line 2 (same size, `color:var(--iris-400)`):** `Then make it forget.`
- **Subcopy (`.lead`):** `Ayin is a free self-scan that shows you your own public exposure — leaked-credential alerts, data-broker listings, your public footprint — scored 0 to 100, with a clear plan to shrink it. You scan only what you've verified is yours. No one can look you up here.`
- **Primary CTA:** `Run my free self-scan →` (`.btn .btn-primary .btn-lg`, → `/signup`).
- **Secondary:** `See a sample report` (`.btn .btn-ghost`, anchor `#sample`).
- **Micro-trust (mono, `--fg-faint`):** `Self-scan only · no card required · exclude-me & delete-everything built in`
- **Visual:** the focusing-iris SVG (§5) in a fixed aspect-ratio box (reserve space → CLS≈0). `aria-hidden`. The score numeral inside the pupil counts `0 → 34` once on load (reduced-motion shows `34` immediately). It is the **same ring component** reused by the real ScorePanel.

### S2 — Asymmetry-flip reassurance band (graft: calm-institutional)
- `.section--band`, centered, single line.
- **H2 (Fraunces):** `Most tools watch people. Ayin hands you the lens.`
- **Sub (`.lead`, centered):** `The person being looked at is the one doing the looking. We only ever scan you — never anyone else.`

### S3 — Trust strip
- Thin row under the band, no headline. Mono chips separated by hairline dividers:
  `Sources, not assertions` · `Publicly available data only` · `Encrypted vault + short retention` · `Every scan audited`

### S4 — How it works (`#how`)
- **Eyebrow:** `HOW IT WORKS`
- **H2:** `From "what's out there?" to "here's the plan." In one scan.`
- `.grid-3`, each a `.card` with mono index `01–03`, faint connecting "lens beam" line behind the numbers:
  1. **`01 · Prove it's you.`** `Confirm the email, phone, or username you want scanned. Ayin only ever looks at identifiers you control — nothing runs until you verify.`
  2. **`02 · Ayin looks — across the open internet.`** `Breach indexes, data-broker listings, and your public web footprint. Publicly available only: nothing behind a login, nothing bought from a leak, nothing about minors.`
  3. **`03 · You get a plan, not a panic.`** `A 0–100 Exposure Score, every finding with its source and capture date, and concrete steps to remove or lock down what's exposed.`
- **Footnote (mono, `--fg-faint`):** `Full pipeline: INPUT → DISCOVERY → RESOLUTION → ENRICHMENT → SCORING → REPORT → REMEDIATION → MONITORING`

### S5 — The agent / Qwen (`#agent`)
- **Eyebrow:** `AUTOPILOT AGENT · POWERED BY QWEN`
- **H2:** `An agent that explains, never accuses.`
- **Sub (`.lead`):** `Ayin's report is written by an autonomous agent powered by Qwen. It reads only your scan's real, sourced findings and explains in plain language what each one means and what to do first — every sentence cites the finding it rests on. It summarizes what's there; it never invents a finding and never decides for you.`
- **Visual:** a faux `NarrativePanel` card mirroring the real component — the `✦ written by Qwen` pill, two plain sentences each ending in a mono `[1]` citation chip, then a "Where to start" mini-list. Reproduce the real guardrail line: `Only a hint — your answer decides.`
- **Guardrail chip (`.pill-iris`):** `Cited or silent — the agent only narrates what it actually retrieved.`

### S6 — Before / After (`#sample`) — the demo wow
- **H2:** `This is what your report looks like.`
- Two-column: left a small framed product screenshot of the real report (ScorePanel + 2 FindingsList rows + Qwen panel); right two stacked state chips:
  `Before — Exposure 72 · 9 things exposed` → `After your fixes — Exposure 31 · plan in motion`
- The score ring animates between states on scroll (reduced-motion → static).
- **Sub:** `Calm by design. We lead with the fix, never a wall of red — even a high score comes with the three things to do first.`
- Inline CTA: `Run yours →` (→ `/signup`).

### S7 — Safety & control (`#safety`) — the differentiator, made loud
- **Eyebrow:** `BUILT TO BE TRUSTED`
- **H2:** `The controls that protect you are the first thing we built.`
- `.grid-2` bento — this section is the **only** one allowed `.card--glow`:
  - **`Exclude me from Ayin`** → `/exclude` — `Don't want to be scannable here at all? Opt out in one step — no account needed, honored permanently.`
  - **`Delete everything`** → `/dashboard` (DataRights) — `One action crypto-shreds your data. We keep findings and your score, never a permanent dossier. Gone means gone.`
  - **`Sources, not assertions`** — `Every finding shows where it came from, when we captured it, and how confident we are. No mystery data.`
  - **`Audited from the first scan`** — `Every scan — and every access to your data, including by our own staff — writes an immutable record.`
- **Closing line:** `We're a self-exposure scanner, not a consumer reporting agency. Ayin can't be used to look someone else up, or for credit, hiring, tenant, or insurance decisions.`

### S8 — Differentiator strip
- **H2 (small):** `Why Ayin.`
- `.grid-3`, positive framing, no competitor names:
  - **`You hold the lens`** — `Self-scan only. We never look someone up for you.`
  - **`Calm, not alarmist`** — `A plan, not a wall of red. Most tools profit from your fear; we profit from your control.`
  - **`Privacy by construction`** — `Short retention, crypto-shred, full audit. We never build a sellable index and never sell your data.`

### S9 — FAQ (`#faq`) — also emits FAQPage JSON-LD
Native `<details>/<summary>` accordion (no-JS, a11y free). The Q&A array is the **single source** shared with the JSON-LD in §7.
1. **Is Ayin free?** — `Yes — the self-scan is free, no card required. Ongoing monitoring and assisted removal are the paid layer, but seeing your full exposure picture once costs nothing.`
2. **Can I scan someone else?** — `No, and that's deliberate. Ayin only scans identifiers you've verified you control. It is not a people-search or background-check tool, and there is no way to look anyone else up — by design.`
3. **Where does the data come from?** — `Only publicly available sources — breach indexes, data-broker listings, and your public web footprint — reached without logging in, defeating a security control, or breaking a site's terms. We never buy breached data or touch anything about minors. Every finding carries its source and a capture date.`
4. **Will you ever show my actual leaked password?** — `Never. We show that a credential was exposed and in which breach — never the plaintext. The fix is the same either way: rotate it and turn on two-factor.`
5. **What happens to my data after a scan?** — `We store your findings and score — not a permanent dossier — encrypted and on a short retention timer. Delete everything in one click and it's crypto-shredded, unrecoverable even by us.`
6. **Is my Exposure Score a judgment of me?** — `No. It measures how exposed and exploitable your data is, from 0–100 — never your character, creditworthiness, or employability, and it can't be used for those decisions.`

### S10 — Final CTA
- `.section--band`, dimmed iris artifact behind, centered.
- **H2 (Fraunces):** `Point the lens at yourself first.`
- **Sub:** `A few minutes. One score. A plan you control.`
- **Primary CTA:** `Run my free self-scan →` · text link: `or read how it works` (`#how`).

---

## 5. Global chrome

### 5.1 The iris mark (logo) — inline SVG concept
An **aperture-iris**: a lens, not a watching eyeball (no lashes, no crosshair). Outer ring + concentric iris ring + cyan→indigo pupil + one upper-left catch-light arc (kindness cue for the survivor persona) + a relaxed open lower curve. `currentColor` so it themes for free; pupil uses a gradient. Ships as `frontend/components/IrisMark.tsx` (`{ size, animate }` props) and as `frontend/app/icon.svg`.

```tsx
// IrisMark.tsx — single source for nav, hero, footer, favicon, ScorePanel ring
export default function IrisMark({ size = 32, animate = false }: { size?: number; animate?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label="Ayin"
         className={animate ? "iris iris--focus" : "iris"}>
      <defs>
        <radialGradient id="ay-pupil" cx="42%" cy="38%" r="70%">
          <stop offset="0%" stopColor="var(--iris-400)" />
          <stop offset="100%" stopColor="var(--indigo-500)" />
        </radialGradient>
      </defs>
      {/* relaxed almond — open lower curve, never a hard slit */}
      <path d="M3 25C9 14 16 10 24 10s15 4 21 15c-6 9-13 12-21 12S9 33 3 25Z"
            fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" opacity=".9"/>
      {/* iris ring */}
      <circle className="iris-ring" cx="24" cy="22" r="9.5" fill="none"
              stroke="currentColor" strokeWidth="1.4" opacity=".55"/>
      {/* pupil = the lens light */}
      <circle className="iris-pupil" cx="24" cy="22" r="5" fill="url(#ay-pupil)"/>
      {/* catch-light: the kindness cue */}
      <path d="M20 18.5a5 5 0 0 1 3-2.2" fill="none" stroke="var(--iris-400)"
            strokeWidth="1.2" strokeLinecap="round" opacity=".9"/>
    </svg>
  );
}
```
```css
/* hero focus gesture + header hover; reduced-motion → instant end-state */
.iris--focus .iris-ring { transform-origin:24px 22px; animation:irisFocus var(--dur-4) var(--ease-iris) both; }
.iris--focus .iris-pupil{ animation:pupilGlow var(--dur-4) var(--ease-iris) both; }
@keyframes irisFocus { from{ transform:scale(1.35); opacity:0;} to{ transform:scale(1); opacity:.55;} }
@keyframes pupilGlow { from{ opacity:.4;} to{ opacity:1;} }
.site-header .iris:hover .iris-ring { transition:transform var(--dur-3) var(--ease-iris); transform:rotate(8deg); }
```

### 5.2 Header / nav — `frontend/components/Header.tsx` (new)
- `.site-header` (sticky, blur, hairline appears on scroll via a tiny `IntersectionObserver`/scroll listener adding `.scrolled`).
- Left: `<IrisMark size={28}/>` + `Ayin` wordmark (Fraunces 540).
- Right (`.nav-links`): `How it works` · `Safety` · `FAQ` · divider · `Sign in` (ghost) · `Run free scan` (`.btn .btn-primary`).
- Mobile (≤760px): mark + a `<details>` sheet (no-JS friendly) with the same links; CTA pinned.
- Logged-in variant (when `app/layout.tsx` sees a session): swap links for `Dashboard` / `Reports` + `Sign out`. Header is rendered in `layout.tsx` above `{children}`.

### 5.3 Footer — extend `frontend/components/Footer.tsx`
Three columns on `.section--band` + base row:
- **Product:** Self-scan · How it works · Safety & control · FAQ
- **Your rights** (verdigris/teal tick treatment, first-class): **Exclude me from Ayin** (`/exclude`) · **Delete my data** · Terms (`/terms`) · Audit & retention (`#safety`)
- **Project:** Qwen AI Hackathon — Track 4 · Status (`/status`) · GitHub
- **Base row (mono, `--fg-faint`), permanent + legally load-bearing on every page:**
  `Ayin — sight, not surveillance.` · `© 2026` · `<IrisMark size={16}/>` · `Self-scan only. Not a consumer reporting agency.`

### 5.4 Sticky mobile CTA
`.sticky-cta` with `Run your free self-scan →`; a small IntersectionObserver toggles `.show` once the hero leaves the viewport.

---

## 6. App-surface restyle checklist (behavior preserved — presentational only)

> Rule: change tokens, classes, and *markup wrappers* only. Do not alter data flow, fetch calls, `StepUpModal`/`TosGate` logic, or any component contract.

### Login / Signup (`AuthForm`, `/login`, `/signup`)
- [ ] Centered card (`.card .card--raised`, max 420px) on `--ink-900` with a faint top-center iris-glow radial; `<IrisMark/>` above the form.
- [ ] Inputs → `.field` styling (44px, `--ink-550` fill, `--glow-iris` focus). Submit → `.btn .btn-primary` full-width.
- [ ] Fraunces title ("Welcome back" / "Start your free self-scan"). Keep reassurance microcopy: `We verify each identifier before anything scans.`

### Dashboard (`/dashboard`)
- [ ] Two-column bento on wide screens: left = `ScanPanel` + `IdentifierManager` (action); right rail = `DataRights` (exclude/delete **visible**, not buried) + `GettingStarted`.
- [ ] Section header in Fraunces: "Your lens."
- [ ] `IdentifierManager`: verified identifiers as mono chips with teal check; unverified muted with "Verify to scan" nudge (reinforces self-scan-only).
- [ ] `GettingStarted`/`IntentCTA`: numbered mono steps matching landing pipeline language.

### Report page (`/report/[scanId]`) — calm is enforced here
- [ ] **Reorder to plan-first** using the existing `onLoaded.hasTopFixes` hook: render `NarrativePanel` "Where to start" + `HardeningChecklist` top-3 **ABOVE** the full `FindingsList`. Final order: `ScorePanel → NarrativePanel (top fixes) → HardeningChecklist → FindingsList → PlannerTrail`.
- [ ] **ScorePanel:** render the digit inside the **same iris ring SVG** as the hero (replace the inline `3rem` digit with an SVG arc filling to `score.overall`, colored by the muted band scale). Mono/`tnum` numeral (`--fs-score`), one-time count-up (`--ease-spring`, suppressed under reduced-motion). Card edge stays a **1px** `bandColor` (now clay/teal/plum, never red); a ≤10% `--down-bg`/`--warn-bg` glow may sit behind the number only. **Promote** the verbatim line `Measures how exposed your data is — never a judgment of you` to a pill under the score, and pair it with `…and here's how to lower it.`
- [ ] **NarrativePanel (Qwen):** keep the `✦ written by Qwen` pill exactly as shipped (continuity with landing). `--ink-550` body, mono attribution + model name, subtle `--grad-card-edge` top hairline. Keep `ERAdvice` "only a hint — your answer decides" subdued.
- [ ] **FindingsList — calm:**
  - Sensitivity = a **10px dot** (`.sev-dot`) in the retuned hue, NO row tint (enforce sensitivity-containment).
  - Add a **word-led pill** next to each finding: `Low / Medium / High / Sensitive` (color supports only) — satisfies WCAG 1.4.1.
  - Source-meta line (`source_name · confidence X% · captured …`) → `.meta` **monospace**.
  - Add a per-finding footer link **`Fix this →`** that jumps to the matching `HardeningChecklist` item (graft: warm-human; closes problem→plan loop).
  - Locked-credential notice keeps `--warn` (amber-clay) edge; **never** plaintext. Empty state ("a quiet footprint is a good result") celebrated in teal `--ok` with a small focused-iris glyph.
- [ ] **HardeningChecklist:** rows with a mono priority tag (`P1/P2`) + per-item effort/impact tag (`2 min · big drop`) (graft: warm-human). Completed → soft `--ok` check; top progress bar "3 of 8 done."
- [ ] **PlannerTrail:** render with the shared `.trail`/`.trail-node` iris-node motif + mono timestamps — visually identical to the landing how-it-works trail (the "agent trail as recurring motif" graft).

### Shared
- [ ] Verify no component hardcodes old hex; all read CSS vars (they do today). Convert any stray hex to `var(--*)`.
- [ ] Sensitivity is never color-only anywhere; the existing `title="sensitivity: …"` is surfaced as a visible word + `aria-label`.

---

## 7. SEO implementation spec

### 7.1 `frontend/app/layout.tsx` — root metadata + fonts + JSON-LD + chrome
```ts
import { Fraunces, Inter, IBM_Plex_Mono } from "next/font/google";
export const fraunces = Fraunces({ subsets:["latin"], display:"swap", axes:["opsz"], weight:["400","500","600"], variable:"--font-fraunces" });
export const inter    = Inter({ subsets:["latin"], display:"swap", weight:["400","500","600","800"], variable:"--font-inter" });
export const plexMono = IBM_Plex_Mono({ subsets:["latin"], display:"swap", weight:["400","500"], variable:"--font-plex-mono" });

export const metadata: Metadata = {
  metadataBase: new URL("https://superayin.com"),
  title: { default: "Ayin — See what the internet knows about you", template: "%s · Ayin" },
  description: "Run a free self-scan to see your public exposure — leaked-credential alerts, data-broker listings, your public footprint — scored 0–100, with a plan to shrink it. Self-scan only.",
  keywords: ["self-exposure scan","what does the internet know about me","check my data breaches free","data broker opt out","personal OSINT scan","exposure score","privacy footprint check"],
  applicationName: "Ayin",
  alternates: { canonical: "/" },
  robots: { index: true, follow: true },
  openGraph: { type:"website", siteName:"Ayin", url:"https://superayin.com", locale:"en_US",
    title:"Ayin — See what the internet knows about you, then make it forget",
    description:"Free privacy self-scan · Self-scan only · Exposure Score 0–100 · a calm plan to shrink it.",
    images:[{ url:"/opengraph-image", width:1200, height:630, alt:"Ayin — see what the internet knows about you" }] },
  twitter: { card:"summary_large_image", title:"Ayin — See what the internet knows about you", description:"Free privacy self-scan. Self-scan only. Exposure Score + a plan to shrink it.", images:["/opengraph-image"] },
};
```
- Add `<html lang="en" className={`${fraunces.variable} ${inter.variable} ${plexMono.variable}`}>`.
- Render `<Header/>` above `{children}`, `<Footer/>` below. Add a tiny inline `<script>` that sets `document.documentElement.classList.add('js')` (enables reveals; no-JS stays visible).
- Emit Organization + WebSite + SoftwareApplication JSON-LD here (site-wide); FAQPage on `/` only.

### 7.2 Per-route metadata
| Route | title | robots |
|---|---|---|
| `/` | (default) | index, follow |
| `/signup` | `Start your free self-scan` | index, follow |
| `/exclude` | `Exclude yourself from Ayin` | index, follow |
| `/terms` | `Terms` | index, follow |
| `/status` | `System status` | **noindex** |
| `/login` | `Sign in` | **noindex, nofollow** |
| `/dashboard` | `Dashboard` | **noindex, nofollow** |
| `/report/[scanId]` | `Your exposure report` | **noindex, nofollow** |
| `/verify-email` | `Verify your email` | **noindex, nofollow** |
| `/verify-identifier` | `Verify identifier` | **noindex, nofollow** |
| `/exclude/confirm` | `Exclusion confirmed` | **noindex, nofollow** |

### 7.3 JSON-LD blocks (emit via `<script type="application/ld+json" dangerouslySetInnerHTML>`; static objects only, no PII)
```json
{
  "@context":"https://schema.org","@type":"Organization",
  "name":"Ayin","url":"https://superayin.com","logo":"https://superayin.com/icon.svg",
  "description":"A privacy self-exposure scanner. See what the open internet exposes about identifiers you control, get an Exposure Score, and a plan to shrink it. Self-scan only.",
  "slogan":"See what the internet knows about you — then make it forget.",
  "sameAs":["https://devpost.com/software/ayin"]
}
```
```json
{ "@context":"https://schema.org","@type":"WebSite",
  "name":"Ayin","url":"https://superayin.com" }
```
> WebSite intentionally omits `potentialAction`/`SearchAction` — there is no people-search; faking one would contradict self-scan-only. Omit `AggregateRating` everywhere — no real reviews.
```json
{
  "@context":"https://schema.org","@type":"SoftwareApplication",
  "name":"Ayin","applicationCategory":"SecurityApplication","operatingSystem":"Web",
  "url":"https://superayin.com",
  "description":"Free OSINT self-exposure scan. See breaches, data-broker listings, and your public footprint for identifiers you control; get a 0–100 Exposure Score and a plan to shrink it. Self-scan only.",
  "offers":{ "@type":"Offer","price":"0","priceCurrency":"USD" },
  "featureList":["Self-scan only","Exposure Score 0–100","Sourced findings","Data-broker opt-out guidance","Qwen-written report","Exclude-me and delete-everything controls"]
}
```
```json
{
  "@context":"https://schema.org","@type":"FAQPage",
  "mainEntity":[
    {"@type":"Question","name":"Is Ayin free?","acceptedAnswer":{"@type":"Answer","text":"Yes — the self-scan is free, no card required. Ongoing monitoring and assisted removal are the paid layer, but seeing your full exposure picture once costs nothing."}},
    {"@type":"Question","name":"Can I scan someone else?","acceptedAnswer":{"@type":"Answer","text":"No, and that's deliberate. Ayin only scans identifiers you've verified you control. It is not a people-search or background-check tool, and there is no way to look anyone else up — by design."}},
    {"@type":"Question","name":"Where does the data come from?","acceptedAnswer":{"@type":"Answer","text":"Only publicly available sources — breach indexes, data-broker listings, and your public web footprint — reached without logging in, defeating a security control, or breaking a site's terms. We never buy breached data or touch anything about minors. Every finding carries its source and a capture date."}},
    {"@type":"Question","name":"Will you ever show my actual leaked password?","acceptedAnswer":{"@type":"Answer","text":"Never. We show that a credential was exposed and in which breach — never the plaintext. The fix is the same either way: rotate it and turn on two-factor."}},
    {"@type":"Question","name":"What happens to my data after a scan?","acceptedAnswer":{"@type":"Answer","text":"We store your findings and score — not a permanent dossier — encrypted and on a short retention timer. Delete everything in one click and it's crypto-shredded, unrecoverable even by us."}},
    {"@type":"Question","name":"Is my Exposure Score a judgment of me?","acceptedAnswer":{"@type":"Answer","text":"No. It measures how exposed and exploitable your data is, from 0–100 — never your character, creditworthiness, or employability, and it can't be used for those decisions."}}
  ]
}
```

### 7.4 `frontend/app/sitemap.ts`
```ts
import type { MetadataRoute } from "next";
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://superayin.com";
  const now = new Date();
  return ["/","/signup","/exclude","/terms"].map((p)=>({ url:`${base}${p}`, lastModified:now,
    changeFrequency:"monthly", priority:p==="/"?1:0.7 }));
}
```

### 7.5 `frontend/app/robots.ts`
```ts
import type { MetadataRoute } from "next";
export default function robots(): MetadataRoute.Robots {
  return { rules:{ userAgent:"*", allow:"/",
    disallow:["/dashboard","/report","/login","/verify-email","/verify-identifier","/exclude/confirm","/status"] },
    sitemap:"https://superayin.com/sitemap.xml" };
}
```

### 7.6 `frontend/app/manifest.ts`
```ts
import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return { name:"Ayin", short_name:"Ayin", description:"Privacy self-exposure scanner. Self-scan only.",
    start_url:"/", display:"standalone", theme_color:"#0b0e14", background_color:"#0b0e14",
    icons:[{ src:"/icon.svg", sizes:"any", type:"image/svg+xml" },
           { src:"/icon-192.png", sizes:"192x192", type:"image/png", purpose:"maskable" },
           { src:"/icon-512.png", sizes:"512x512", type:"image/png", purpose:"maskable" }] };
}
```

### 7.7 Favicon + OG image
- **Favicon:** `frontend/app/icon.svg` — the iris mark with `currentColor` resolved to `#6fd2ff` (renders crisp light/dark). Plus `frontend/app/apple-icon.png`.
- **OG image:** `frontend/app/opengraph-image.tsx` via `next/og` `ImageResponse` (edge), 1200×630, **rendered from a static LIGHT variant** (paper bg even on the dark site, per grafts): the iris mark, Fraunces headline "See what the internet knows about you / then make it forget", mono footer `superayin.com · self-scan only`. No PII. Headline copy stays in sync because it's generated from code.

### 7.8 a11y / semantic-HTML / Core-Web-Vitals checklist
- [ ] One `<h1>` per page; `<section aria-labelledby>` + single `<h2>`; landmarks `<header><main><footer><nav aria-label="Primary">`; skip-to-content link.
- [ ] FAQ = native `<details>/<summary>`.
- [ ] Severity never color-only (word + `aria-label`); focus-visible ring everywhere; all CTAs are real `<a>`/`<button>` with text; decorative iris `aria-hidden`.
- [ ] Contrast ≥ 4.5:1 body / ≥ 3:1 large+UI — verify `--fg-dim` on `--ink-700`/`--ink-900` (passes) before ship.
- [ ] Landing **static** (`force-static`), zero API dependency → survives API outage. Fonts via `next/font` self-hosted `display:swap` (no FOUT/CLS); preload display weights only. Hero iris is **inline SVG** (no LCP image; LCP element = H1 text). Reserve the iris box aspect-ratio (CLS≈0). Targets: LCP < 1.5s, CLS < 0.05, INP < 200ms.
- [ ] `prefers-reduced-motion` honored globally (token block); count-up/iris focus render to end-state.

---

## 8. File-by-file implementation plan (ordered; tokens first, demo never breaks)

> Each step is independently shippable; after step 1 the whole app reskins for free via aliases, after step 5 you have an award-worthy front door with the working demo untouched behind it.

1. **`frontend/app/globals.css`** — replace `:root` with §2 tokens (aliases included); append §3 primitive utility layer. *(App reskins instantly; demo safe.)*
2. **`frontend/app/layout.tsx`** — wire `next/font` (Fraunces/Inter/Plex Mono) + variable classes on `<html>`; add §7.1 metadata; emit Organization/WebSite/SoftwareApplication JSON-LD; add `.js` script; render `<Header/>` + `<Footer/>`.
3. **`frontend/components/IrisMark.tsx`** *(new)* — the inline-SVG iris (§5.1), `{size, animate}` props.
4. **`frontend/components/Header.tsx`** *(new)* — sticky nav, mobile `<details>` sheet, logged-in variant, scroll-shadow observer (§5.2).
5. **`frontend/app/page.tsx`** — delete `force-dynamic`/`fetchHealth`; set `force-static`; build the 11-section landing (§4) with the FAQPage JSON-LD; add sticky-CTA observer.
6. **`frontend/app/status/page.tsx`** *(new)* — move the old system-status widget here (may call `fetchHealth`); `noindex`.
7. **`frontend/components/Footer.tsx`** — three columns + permanent legal base row + IrisMark (§5.3).
8. **`frontend/app/sitemap.ts`** *(new)* — §7.4.
9. **`frontend/app/robots.ts`** *(new)* — §7.5.
10. **`frontend/app/manifest.ts`** *(new)* — §7.6.
11. **`frontend/app/icon.svg`** *(new)* + **`apple-icon.png`** + **`icon-192.png`/`icon-512.png`** — favicon set (§7.7).
12. **`frontend/app/opengraph-image.tsx`** *(new)* — `next/og` ImageResponse, light variant (§7.7).
13. **`frontend/components/ScorePanel.tsx`** — iris score-ring (reuse IrisMark ring), mono `tnum` numeral, count-up, "not a judgment of you" pill, calm band edge (§6).
14. **`frontend/components/FindingsList.tsx`** — `.sev-dot` containment, word-led severity pill, `.meta` mono provenance, `Fix this →` link (§6).
15. **`frontend/components/NarrativePanel.tsx`** — Qwen pill continuity + mono attribution (§6).
16. **`frontend/components/HardeningChecklist.tsx`** — `P1/P2` tags + effort/impact tags + progress bar (§6).
17. **`frontend/components/PlannerTrail.tsx`** — shared `.trail`/`.trail-node` motif + mono timestamps (§6).
18. **`frontend/app/report/[scanId]/page.tsx`** — reorder to plan-first via `onLoaded.hasTopFixes` (§6).
19. **`frontend/components/AuthForm.tsx`** + **`/login`,`/signup`** — `.field`/`.btn-primary` card + IrisMark (§6).
20. **`frontend/app/dashboard/page.tsx`** + `IdentifierManager`/`DataRights`/`GettingStarted` — bento + visible rights rail (§6).
21. **Per-route `metadata` exports** on `/signup /exclude /terms /login /dashboard /report/[scanId] /verify-* /exclude/confirm /status` (§7.2).

---

## 9. Definition of done

- [ ] **Build/typecheck:** `cd frontend && npm run build` and `npm run lint`/`tsc --noEmit` pass clean.
- [ ] **Demo intact:** login → create/verify identifier → run scan → view report works end-to-end (the load-bearing flow), before and after the restyle.
- [ ] **API-outage graceful:** with the API stopped, `/` still renders fully (no `fetchHealth` on landing); only `/status` shows "unreachable."
- [ ] **Token aliases present:** `--bg --surface --border --text --text-dim --accent --ok --warn --down` all resolve; no component references a removed/renamed var; no stray hardcoded hex.
- [ ] **Calm gates pass code review:** sensitivity color confined to dot/1px-edge/≤10% well (no card/row floods); every severity has a word label; report opens plan-first (top-3 fixes above FindingsList); critical = plum-rose, never `#f87171`; no plaintext credentials shown.
- [ ] **Brand/legal:** no copy implies looking up another person / people-search / background-check; footer legal line `Self-scan only. Not a consumer reporting agency.` present site-wide.
- [ ] **SEO assertions:** `/sitemap.xml` lists only `/ /signup /exclude /terms`; `/robots.txt` disallows dashboard/report/login/verify/exclude-confirm/status; `/opengraph-image` returns a 1200×630 image; private routes return `noindex`; Organization + WebSite + SoftwareApplication + FAQPage JSON-LD validate (no AggregateRating, no SearchAction).
- [ ] **a11y:** one `<h1>`/page, landmarks + skip-link present, focus-visible rings, severity not color-only, `prefers-reduced-motion` disables iris focus/count-up; axe/Lighthouse a11y ≥ 95.
- [ ] **CWV (preview, mid hardware):** LCP < 1.5s, CLS < 0.05, INP < 200ms on `/`; fonts self-hosted, no FOUT/layout shift.
- [ ] **Preview:** `npm run dev` (or built preview) screenshot of hero, plan-first report, and safety bento reviewed against §1–§5.

---

**Grounding note:** verified against the live code — current `globals.css` defines exactly the 8 legacy vars this spec aliases (`--bg/--surface/--border/--text/--text-dim/--accent/--ok/--warn/--down`); current `page.tsx` is the dev placeholder with `export const dynamic = "force-dynamic"` + `fetchHealth()` (both removed in step 5); `layout.tsx` already renders `<Footer/>` (Header added in step 2). The token-alias approach means components reading these vars inherit the redesign with zero contract changes.

Key files (absolute): `C:\Users\Ong Jun Kai\OneDrive\Documents\Claude\Projects\Ayin\frontend\app\globals.css` · `...\frontend\app\layout.tsx` · `...\frontend\app\page.tsx` · `...\frontend\components\Footer.tsx` (+ new `Header.tsx`, `IrisMark.tsx`) · `...\frontend\components\{ScorePanel,FindingsList,NarrativePanel,HardeningChecklist,PlannerTrail,AuthForm}.tsx` · new `...\frontend\app\{status\page.tsx,sitemap.ts,robots.ts,manifest.ts,icon.svg,opengraph-image.tsx}`.