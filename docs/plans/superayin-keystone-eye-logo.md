# SuperAyin logo — "keystone eye" decision record (2026-07-13)

Third-generation mark. Replaces "audited iris" (2026-07-12), which the user rejected as ugly
and which shipped a real rendering bug: `.site-header .iris-link:hover .iris-ring` rotated the
gauge ring around the SVG origin (0,0) — `transform-origin` was only set on the *animated*
variant — so the ring visibly swung out of the eye on hover. The open gauge gap also read as a
half-drawn circle at header size.

## Mark history (do not revisit)

1. **Iris eye** (2026-06-21, Fraunces era) — superseded by Sentinel.
2. **ʿAyin glance** (2026-07-11) — rejected: read as a swoosh/checkmark. ʿAyin letterforms
   failed twice across 18 variants; never retry.
3. **Audited iris** (2026-07-12) — rejected: ugly + broken hover (above).
4. **Keystone eye** (this) — chosen by the user from a 4-candidate board
   (lens / keystone eye / A-perture monogram / viewfinder), judged at 140/48/28/16px,
   dark + light, lockup + header context.

## Why this one survives what the others didn't

- **No strokes, no gaps**: the eye is bold negative space cut from a solid tile — nothing can
  half-render, and there is no gauge gap to misread as a glitch.
- **Self-contained tile**: the mark carries its own background; it never depends on page
  color, so dark/light/OG/favicon are the same asset logic.
- **16px-proof**: vesica + solid pupil survive favicon size; the light-catch dot drops below
  24px (`detailed` switch) instead of degrading.

## Geometry (viewBox 0 0 48 48 — single source `components/IrisMark.tsx`)

- Tile: `rect x3 y3 w42 h42 rx13`, linear gradient `--iris-500 → --indigo-500` (45°).
- Vesica (eye white): `M9.5 24 C15 14.6 33 14.6 38.5 24 C33 33.4 15 33.4 9.5 24 Z`, `#FFFFFF`.
- Pupil: `cx24 cy24 r5.8` `#0F172A` (literal — sits on the white vesica in both themes).
- Light catch: `cx26 cy22 r1.7` white, ≥24px only. Micro variant: pupil `r6.2`, no catch.
- Favicon `app/icon.svg`: same geometry, tile `x2 y2 w44 h44 rx13`, literal hex.
- OG `app/opengraph-image.tsx`: same geometry, SOLID `#2563EB` tile (Satori: no gradients).

## Motion rules (globals.css)

- `.eye-glyph { transform-box: fill-box; transform-origin: center; }` — the load-bearing fix;
  any future transform on SVG children MUST keep `transform-box: fill-box`.
- Header hover = one wink (`ayWink` scaleY, 0.5s, correctly anchored). Entrance (`animate`
  prop, hero only) = glyph scale-in. Both sit behind the global reduced-motion gate.
