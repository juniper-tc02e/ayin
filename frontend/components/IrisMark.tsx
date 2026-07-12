/**
 * The Ayin mark: "the audited iris" — a calm almond eye (ʿayin means *eye*)
 * whose iris is the product's own Exposure-Score ring: an open gauge arc with
 * a solid core. The eye is YOURS looking back — heavy-lidded, level, never a
 * surveillance eyeball (no lashes, no crosshair) — and the gauge-iris ties the
 * brand to the score ring users see in every report. Lids use currentColor so
 * the mark themes for free; the iris is trust-blue. Below 24px the gauge
 * detail collapses to a solid pupil so the favicon and micro uses stay crisp.
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
  // Unique gradient id per instance so multiple marks on a page don't collide.
  const gid = `ay-pupil-${size}-${animate ? "a" : "s"}`;
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
        <radialGradient id={gid} cx="38%" cy="34%" r="75%">
          <stop offset="0%" stopColor="var(--iris-400)" />
          <stop offset="100%" stopColor="var(--indigo-500)" />
        </radialGradient>
      </defs>
      {/* lids: heavy upper glance sweeping past the corner, light lower lid */}
      <g fill="none" stroke="currentColor" strokeLinecap="round">
        <path d="M4 24 C12.5 12.5 35 12 44 22.5" strokeWidth="5.2" />
        <path d="M9 27.5 C16.5 33.8 31.5 34 39.5 27.5" strokeWidth="2.9" opacity=".92" />
      </g>
      {detailed ? (
        <>
          {/* iris = the Exposure-Score gauge: open ring + core */}
          <circle
            className="iris-ring"
            cx="26"
            cy="23.5"
            r="7.2"
            fill="none"
            stroke="var(--iris-500)"
            strokeWidth="2.7"
            strokeLinecap="round"
            strokeDasharray="37.3 7.94"
            strokeDashoffset="9.43"
          />
          <circle className="iris-pupil" cx="26" cy="23.5" r="3.2" fill={`url(#${gid})`} />
        </>
      ) : (
        /* micro sizes: solid pupil keeps the eye legible at 16px */
        <circle className="iris-pupil" cx="25.5" cy="23.7" r="6" fill={`url(#${gid})`} />
      )}
    </svg>
  );
}
