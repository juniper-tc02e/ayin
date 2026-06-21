import { ImageResponse } from "next/og";

export const alt = "Ayin — see what the internet knows about you";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// A static LIGHT (paper) social card even though the site runs dark — brighter
// previews, headline generated from code so it never drifts from the site. The
// iris is drawn with nested divs (Satori-reliable, no gradients-in-svg risk).
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
          background: "#f6f8fb",
          padding: "72px 80px",
          fontFamily: "sans-serif",
        }}
      >
        {/* top: mark + wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          <div
            style={{
              width: 86,
              height: 86,
              borderRadius: 999,
              border: "4px solid #2b8fe0",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 999,
                background: "linear-gradient(135deg, #2b8fe0, #7c6cff)",
              }}
            />
          </div>
          <div style={{ fontSize: 44, fontWeight: 700, color: "#0e1722" }}>Ayin</div>
        </div>

        {/* headline */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 68, fontWeight: 800, color: "#0e1722", lineHeight: 1.05, letterSpacing: -1 }}>
            See what the internet
          </div>
          <div style={{ fontSize: 68, fontWeight: 800, color: "#0e1722", lineHeight: 1.05, letterSpacing: -1 }}>
            knows about you.
          </div>
          <div style={{ fontSize: 68, fontWeight: 800, color: "#1f7fd1", lineHeight: 1.1, letterSpacing: -1 }}>
            Then make it forget.
          </div>
        </div>

        {/* footer */}
        <div style={{ display: "flex", justifyContent: "space-between", color: "#51607a", fontSize: 28 }}>
          <div>superayin.com</div>
          <div>Self-scan only · free privacy scan</div>
        </div>
      </div>
    ),
    { ...size }
  );
}
