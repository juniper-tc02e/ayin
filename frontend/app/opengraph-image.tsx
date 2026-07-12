import { ImageResponse } from "next/og";

export const alt = "Ayin — see what the internet knows about you";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Sentinel-dark social card — brand-consistent with the site (ink-900 navy,
// trust-blue accent, single emerald chip). Headline is generated from code so
// it never drifts from the site. The audited-iris mark is drawn as inline SVG
// with SOLID colors only (Satori-reliable; no gradients inside svg).
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0F172A",
          padding: "72px 80px",
          fontFamily: "sans-serif",
        }}
      >
        {/* top: mark + wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          <svg width={86} height={86} viewBox="0 0 48 48">
            <path
              d="M4 24 C12.5 12.5 35 12 44 22.5"
              fill="none"
              stroke="#F1F5F9"
              strokeWidth="5.2"
              strokeLinecap="round"
            />
            <path
              d="M9 27.5 C16.5 33.8 31.5 34 39.5 27.5"
              fill="none"
              stroke="#F1F5F9"
              strokeWidth="2.9"
              strokeLinecap="round"
              opacity={0.92}
            />
            <circle
              cx="26"
              cy="23.5"
              r="7.2"
              fill="none"
              stroke="#3B82F6"
              strokeWidth="2.7"
              strokeLinecap="round"
              strokeDasharray="37.3 7.94"
              strokeDashoffset="9.43"
            />
            <circle cx="26" cy="23.5" r="3.2" fill="#60A5FA" />
          </svg>
          <div style={{ fontSize: 46, fontWeight: 700, color: "#F1F5F9" }}>Ayin</div>
        </div>

        {/* headline */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 68, fontWeight: 800, color: "#F1F5F9", lineHeight: 1.05, letterSpacing: -1 }}>
            See what the internet
          </div>
          <div style={{ fontSize: 68, fontWeight: 800, color: "#F1F5F9", lineHeight: 1.05, letterSpacing: -1 }}>
            knows about you.
          </div>
          <div style={{ fontSize: 68, fontWeight: 800, color: "#60A5FA", lineHeight: 1.1, letterSpacing: -1 }}>
            Then make it forget.
          </div>
        </div>

        {/* footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "#97A6BC",
            fontSize: 28,
          }}
        >
          <div>superayin.com</div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div
              style={{
                display: "flex",
                padding: "6px 18px",
                borderRadius: 10,
                background: "#22C55E",
                color: "#04120A",
                fontWeight: 700,
                fontSize: 24,
              }}
            >
              Free self-scan
            </div>
            <div>Self-scan only</div>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
