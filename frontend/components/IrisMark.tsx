/**
 * The Ayin mark: "the keystone eye" — a bold white eye cut as NEGATIVE SPACE
 * from a solid trust-blue tile (ʿayin means *eye*; the eye is YOURS, looking
 * back). Third-generation mark, designed for robustness first: no strokes, no
 * gauge gaps, nothing that can half-render or swing on a bad transform-origin
 * (the failure modes of the two prior marks). Solid vesica + pupil stay
 * legible at 16px. The tile means the mark never depends on page background;
 * lids/whites are literal colors, not currentColor, so dark/light both work.
 * Single source for nav, hero, footer, and auth pages (favicon: app/icon.svg,
 * social card: app/opengraph-image.tsx — keep their geometry in sync).
 */
export default function IrisMark({
  size = 32,
  animate = false,
  title = "Ayin",
  decorative = false,
}: {
  size?: number;
  animate?: boolean;
  title?: string;
  // When next to visible "Ayin" text (header/footer), pass decorative so screen
  // readers don't announce the mark redundantly.
  decorative?: boolean;
}) {
  // Deterministic per-variant gradient id: same-variant collisions are
  // harmless (identical defs), and SSR/client markup stays stable.
  const gid = `ay-tile-${size}-${animate ? "a" : "s"}`;
  const detailed = size >= 24;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : title}
      aria-hidden={decorative || undefined}
      className={animate ? "iris iris--focus" : "iris"}
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--iris-500)" />
          <stop offset="100%" stopColor="var(--indigo-500)" />
        </linearGradient>
      </defs>
      <rect x="3" y="3" width="42" height="42" rx="13" fill={`url(#${gid})`} />
      {/* the eye: white vesica negative space + solid pupil (+ light catch ≥24px) */}
      <g className="eye-glyph">
        <path d="M9.5 24 C15 14.6 33 14.6 38.5 24 C33 33.4 15 33.4 9.5 24 Z" fill="#FFFFFF" />
        {detailed ? (
          <>
            <circle className="iris-pupil" cx="24" cy="24" r="5.8" fill="#0F172A" />
            <circle cx="26" cy="22" r="1.7" fill="#FFFFFF" />
          </>
        ) : (
          /* micro sizes: bigger pupil, no catch — keeps 16px crisp */
          <circle className="iris-pupil" cx="24" cy="24" r="6.2" fill="#0F172A" />
        )}
      </g>
    </svg>
  );
}
