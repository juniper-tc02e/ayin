/**
 * The Ayin mark: the ʿayin glance — a monogram of the Hebrew letter ע ("ayin",
 * literally "eye"). The letter's long arm sweeps from upper-right down through
 * the baseline foot; the second arm is flattened into a lower lid; the pupil
 * rests free in the counter. Reads as a calm, heavy-lidded glance — an eye
 * that is YOURS looking back, never a surveillance eyeball (no lashes, no
 * crosshair). Strokes use currentColor so it themes for free; the pupil is a
 * trust-blue gradient. Single source for nav, hero, footer, and favicon.
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
      {/* the ע long arm: upper-right sweep through the baseline foot */}
      <g
        className="iris-ring"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.6"
        strokeLinecap="round"
      >
        <path d="M40 12 C36 19 31 25 25.5 28.8 C20.5 32.5 15 35.4 9.5 36.2" />
        {/* the second arm, flattened into the lower lid */}
        <path d="M8 20 C12 24 17.5 27 24 28.9" opacity=".92" />
      </g>
      {/* pupil = the lens light, free in the counter */}
      <circle className="iris-pupil" cx="26" cy="20.6" r="4.3" fill={`url(#${gid})`} />
    </svg>
  );
}
