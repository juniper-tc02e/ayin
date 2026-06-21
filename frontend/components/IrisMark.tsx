/**
 * The Ayin mark: an aperture-iris — a lens, not a watching eyeball (no lashes,
 * no crosshair). A relaxed almond with an open lower curve + an upper-left
 * catch-light (the "kindness cue" for the survivor persona) so it reads as an
 * eye that is YOURS. Uses currentColor so it themes for free; the pupil is a
 * cyan->indigo gradient. Single source for nav, hero, footer, and favicon.
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
        <radialGradient id={gid} cx="42%" cy="38%" r="70%">
          <stop offset="0%" stopColor="var(--iris-400)" />
          <stop offset="100%" stopColor="var(--indigo-500)" />
        </radialGradient>
      </defs>
      {/* relaxed almond — open lower curve, never a hard slit */}
      <path
        d="M3 25C9 14 16 10 24 10s15 4 21 15c-6 9-13 12-21 12S9 33 3 25Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        opacity=".9"
      />
      {/* iris ring */}
      <circle
        className="iris-ring"
        cx="24"
        cy="22"
        r="9.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        opacity=".55"
      />
      {/* pupil = the lens light */}
      <circle className="iris-pupil" cx="24" cy="22" r="5" fill={`url(#${gid})`} />
      {/* catch-light: the kindness cue */}
      <path
        d="M20 18.5a5 5 0 0 1 3-2.2"
        fill="none"
        stroke="var(--iris-400)"
        strokeWidth="1.2"
        strokeLinecap="round"
        opacity=".9"
      />
    </svg>
  );
}
