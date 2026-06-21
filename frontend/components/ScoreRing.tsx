"use client";

import { useEffect, useId, useRef, useState } from "react";

/**
 * The Exposure Score, drawn as an iris-aperture ring with the numeral in its
 * pupil. The SAME component powers the marketing hero (counts up once on load)
 * and the real ScorePanel (animates to the scored value) — one signature asset,
 * one calm reading of the number. Color follows the calm band scale (plum-rose
 * at the top, never fire-red). Count-up + arc sweep are suppressed under
 * prefers-reduced-motion (the end-state renders immediately).
 */

const R = 52;
const C = 2 * Math.PI * R;

/** Calm band color, matching ScorePanel.bandColor (via CSS vars/aliases). */
export function bandColor(score: number): string {
  if (score >= 80) return "var(--sev-critical)";
  if (score >= 55) return "var(--sev-high)";
  if (score >= 30) return "var(--iris-400)";
  return "var(--sev-low)";
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export default function ScoreRing({
  value,
  size = 168,
  label = "Exposure Score",
  sublabel = "0–100",
  animate = true,
}: {
  value: number;
  size?: number;
  label?: string;
  sublabel?: string;
  animate?: boolean;
}) {
  const target = Math.max(0, Math.min(100, Math.round(value)));
  const [shown, setShown] = useState(animate ? 0 : target);
  const rafRef = useRef<number | null>(null);
  // Per-instance gradient id (two rings can render on one page). Strip colons
  // from useId so the url(#…) fragment reference stays clean.
  const gid = `ring-pupil-${useId().replace(/:/g, "")}`;

  useEffect(() => {
    if (!animate || prefersReducedMotion()) {
      setShown(target);
      return;
    }
    const start = performance.now();
    const dur = 680;
    const from = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(Math.round(from + (target - from) * eased));
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, animate]);

  const color = bandColor(target);
  const offset = C * (1 - shown / 100);

  return (
    <div
      style={{ position: "relative", width: size, height: size, flexShrink: 0 }}
      role="img"
      aria-label={`${label}: ${target} out of 100`}
    >
      <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden>
        <defs>
          <radialGradient id={gid} cx="42%" cy="38%" r="70%">
            <stop offset="0%" stopColor="var(--iris-400)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--indigo-500)" stopOpacity="0.02" />
          </radialGradient>
        </defs>
        {/* track */}
        <circle cx="60" cy="60" r={R} fill="none" stroke="var(--line)" strokeWidth="8" />
        {/* calm aura behind the numeral */}
        <circle cx="60" cy="60" r="40" fill={`url(#${gid})`} />
        {/* progress arc */}
        <circle
          cx="60"
          cy="60"
          r={R}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={offset}
          transform="rotate(-90 60 60)"
          style={{ transition: "stroke-dashoffset var(--dur-4) var(--ease-spring)" }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            fontSize: size * 0.3,
            lineHeight: 1,
            color,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {shown}
        </span>
        <span className="meta" style={{ marginTop: 4, fontSize: "0.62rem", letterSpacing: ".04em" }}>
          {label}
        </span>
        <span style={{ fontSize: "0.6rem", color: "var(--fg-faint)" }}>{sublabel}</span>
      </div>
    </div>
  );
}
