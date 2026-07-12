# SuperAyin "audited iris" — logo redesign + visual-system deltas (2026-07-12)

Supersedes the **logo section only** of `superayin-sentinel-redesign-spec.md` (2026-07-11).
Everything else in the Sentinel spec (tokens, type, buttons, voice) remains the contract, with
the bounded additions recorded here. Driven by the 2026-07-12 product review
(`docs/reviews/2026-07-12-superayin-product-review.md`).

## Logo — decision record

**Problem:** the ʿayin-glance mark (V14, 2026-07-11) read as a blue swoosh/checkmark at header
size — the letterform never survived as an *eye*.

**Process:** 4 rendered rounds, 26 geometry variants, each judged at 140/48/32/16px + favicon
tile + wordmark lockup, in dark, light, AND mono. Failure modes established en route:

- ʿayin letterforms (2 attempts across both redesigns) read as lowercase "y" — **retired for good**.
- Round lens + raised brow reads *startled webcam*; lid-chord-through-circle reads *smiling mouth*;
  ring-with-gap alone reads *loading spinner*. The almond is the only frame that reliably reads
  "eye" at every size.

**Winner: V9b — "the audited iris."** A calm almond glance whose iris is the product's own
Exposure-Score gauge: an open ring + solid core. The eye is yours looking back (no lashes, no
crosshair — never a surveillance eyeball), and the gauge-iris ties the brand to the score ring
in every report. No competitor draws its gauge into its eye.

**Master geometry** (viewBox 0 0 48 48):

- upper lid `M4 24 C12.5 12.5 35 12 44 22.5` — stroke `currentColor` 5.2, round cap
- lower lid `M9 27.5 C16.5 33.8 31.5 34 39.5 27.5` — stroke 2.9, opacity .92
- iris ring: circle (26, 23.5) r 7.2 — stroke `--iris-500` 2.7, `stroke-dasharray 37.3 7.94`,
  **`stroke-dashoffset 9.43`** (gap at upper-right). Dashoffset, NOT an SVG `transform` — CSS
  hover/entrance transforms override presentation-attribute transforms and would snap the gap.
- core: circle (26, 23.5) r 3.2 — radial gradient `--iris-400 → --indigo-500`

**Small-size variant** (< 24px, and `app/icon.svg`): same lids (5.4/3.2 in the favicon for
16px weight), solid pupil r 6 at (25.5, 23.7), no gauge detail.

**Files:** `components/IrisMark.tsx` (contract unchanged: `{size, animate, title, decorative}`;
detail threshold at `size >= 24`) · `app/icon.svg` · `app/opengraph-image.tsx` (solid colors,
Satori-safe) · `globals.css` `.iris--focus` transform-origin moved to 26px 23.5px. Usage sizes
today: 56 hero CTA / 44 auth / 28 header / 24 footer / 16 footer-legal.

## Visual-system deltas (review-driven, Linear-referenced)

Aesthetic reference locked from styles.refero.design (Linear, "midnight precision instrument") —
adopted as *discipline*, not as colors (Sentinel tokens stay):

1. **One gradient moment only** — `.section--hero` atmospheric radial floor (trust-blue/indigo);
   every other section stays flat. Don't add ambient tints per-card.
2. **Hairline edge definition** — `.section--band` gets `border-block: 1px solid var(--line)`.
3. **Container chrome differentiated by content role:**
   `.card` (default) · `.card--glow` (escalated: the Qwen narrative, SAFETY controls) ·
   `.card--never` (outlined refusal chrome, transparent fill) · `.proof-row` (hairline-divided
   guarantee strip — facts don't get cards).
4. **App shell measure** — `--mw-app: 960px` + `main.main-app` for dashboard/report;
   `.report-lead` puts ScorePanel + NarrativePanel side-by-side ≥1024px. `--mw-read` (760px)
   remains for long-form reading only.
5. **Hero readout** — `.hero-readout` panel (ring + `.readout-bar` category bars) replaces the
   lone floating ScoreRing.
6. Wordmark lockup: `.brand` 700 / -0.02em / line-height 1.

## Landing information architecture (delta)

Section order now: Hero → Proof row (self-scan · shows-its-work · score) → How it works →
**"Every scan explains itself"** (S3.5 — AGENT ACTIVITY sample trail mirroring the live
PlannerTrail, `✦ audited · AI-attributed` pill, no invented data/timestamps) → What we find →
Score → Safety floor → FAQ → CTA. Rationale: lead with the two market-unique assets
(review: competitive dimension), give the AI story a public stage for hackathon judging.

**Copy rule added:** never claim a capability *cannot exist* ("no lookup path exists") — claim the
enforcement ("refused at the gate and audited"), which stays true if consent-gated T1 ever flips on.
