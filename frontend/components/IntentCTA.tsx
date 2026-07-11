"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type IntentState = { monitoring: boolean; removal: boolean };

export default function IntentCTA({
  scanId,
  hasBrokerFindings,
}: {
  scanId: string;
  hasBrokerFindings: boolean;
}) {
  const [state, setState] = useState<IntentState | null>(null);

  useEffect(() => {
    api<IntentState>("/intent").then(setState).catch(() => {});
  }, []);

  async function join(kind: "monitoring" | "removal") {
    try {
      const next = await api<IntentState>("/intent", {
        method: "POST",
        body: { kind, scan_id: scanId },
      });
      setState(next);
    } catch {
      /* non-fatal */
    }
  }

  if (!state) return null;

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Watch for changes</h2>
      <p className="dim" style={{ marginTop: 0, fontSize: "0.9rem" }}>
        Exposure isn&apos;t static — new breaches and broker re-listings happen.
        We&apos;re building continuous monitoring and done-for-you removal; raising your
        hand tells us to prioritize it (and gets you in first).
      </p>
      <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
        {state.monitoring ? (
          <span style={{ color: "var(--ok)", fontSize: "0.9rem" }}>
            ✓ On the monitoring waitlist — we&apos;ll email when it&apos;s live
          </span>
        ) : (
          <button style={ctaStyle} onClick={() => join("monitoring")}>
            Watch for new exposure
          </button>
        )}
        {hasBrokerFindings &&
          (state.removal ? (
            <span style={{ color: "var(--ok)", fontSize: "0.9rem" }}>
              ✓ On the removal waitlist
            </span>
          ) : (
            <button style={ctaStyle} onClick={() => join("removal")}>
              Remove these listings for me
            </button>
          ))}
      </div>
      <p className="dim" style={{ fontSize: "0.75rem", margin: "0.6rem 0 0" }}>
        Until then: re-scan periodically, and use the manual opt-out steps above — they
        work today.
      </p>
    </div>
  );
}

const ctaStyle: React.CSSProperties = {
  padding: "0.5rem 1rem",
  background: "var(--accent)",
  color: "var(--on-iris)",
  border: "none",
  borderRadius: 8,
  fontWeight: 600,
  cursor: "pointer",
};
