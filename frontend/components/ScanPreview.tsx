"use client";

import { useEffect, useState } from "react";
import { api, ScanPreview as Preview } from "@/lib/api";

export default function ScanPreview({ refreshKey }: { refreshKey: number }) {
  const [preview, setPreview] = useState<Preview | null>(null);

  useEffect(() => {
    api<Preview>("/scans/preview").then(setPreview).catch(() => {});
  }, [refreshKey]);

  if (!preview) return null;

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>What we&apos;ll check — and why</h2>

      {preview.blockers.length > 0 && (
        <div style={{ marginBottom: "0.6rem" }}>
          {preview.blockers.map((b) => (
            <p key={b} style={{ margin: "0.2rem 0", color: "var(--warn)", fontSize: "0.9rem" }}>
              ○ {b}
            </p>
          ))}
        </div>
      )}

      {preview.connectors.map((c) => (
        <div key={c.id} className="status-row" style={{ alignItems: "baseline", padding: "0.25rem 0" }}>
          <span className="dot ok" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: "0.9rem" }}>
            <strong>{c.name}</strong> <span className="dim">— {c.why}</span>
          </span>
        </div>
      ))}

      {preview.seeds.length > 0 && (
        <p className="dim" style={{ fontSize: "0.8rem", margin: "0.6rem 0 0" }}>
          Using:{" "}
          {preview.seeds.map((s, i) => (
            <span key={i} title={s.reason} style={{ opacity: s.will_scan ? 1 : 0.5 }}>
              {s.will_scan ? "✓" : "✗"} {s.kind}:{s.value}
              {i < preview.seeds.length - 1 ? " · " : ""}
            </span>
          ))}
        </p>
      )}
      {preview.ready && (
        <p className="dim" style={{ fontSize: "0.8rem", margin: "0.4rem 0 0" }}>
          Estimated time: usually under {Math.max(preview.eta_seconds, 5)} seconds — results
          stream in as each source finishes.
        </p>
      )}
    </div>
  );
}
