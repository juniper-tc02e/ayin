"use client";

import { useEffect, useState } from "react";
import { api, ScoreData } from "@/lib/api";
import ScoreRing, { bandColor } from "@/components/ScoreRing";

const CATEGORY_LABELS: Record<string, string> = {
  credential: "Credentials",
  broker: "Brokers",
  social: "Social",
  records: "Records",
  linkage: "Linkage",
};

export default function ScorePanel({
  scanId,
  refreshKey,
}: {
  scanId: string;
  refreshKey: number;
}) {
  const [score, setScore] = useState<ScoreData | null>(null);
  const [showContributors, setShowContributors] = useState(false);

  useEffect(() => {
    api<ScoreData>(`/scans/${scanId}/score`).then(setScore).catch(() => setScore(null));
  }, [scanId, refreshKey]);

  if (!score) return null;

  return (
    <div className="card" style={{ borderColor: bandColor(score.overall) }}>
      <div style={{ display: "flex", gap: "1.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <ScoreRing value={score.overall} size={132} label="Exposure Score" sublabel="0–100" />
        <div style={{ flex: 1, minWidth: 220 }}>
          <p style={{ margin: "0 0 0.5rem" }}>{score.verdict}</p>
          <span
            className="pill"
            style={{ marginBottom: "0.6rem", color: "var(--sev-low)", borderColor: "color-mix(in srgb, var(--sev-low) 40%, transparent)" }}
          >
            Measures your data&apos;s exposure — never you · and here&apos;s how to lower it
          </span>
          {Object.entries(score.subscores).map(([cat, value]) => (
            <div key={cat} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: 3 }}>
              <span className="dim" style={{ fontSize: "0.75rem", width: 86 }}>
                {CATEGORY_LABELS[cat] ?? cat}
              </span>
              <div style={{ flex: 1, height: 6, background: "var(--bg)", borderRadius: 3 }}>
                <div
                  style={{
                    width: `${value}%`,
                    height: "100%",
                    borderRadius: 3,
                    background: bandColor(value),
                    transition: "width 0.4s",
                  }}
                />
              </div>
              <span className="dim" style={{ fontSize: "0.75rem", width: 24, textAlign: "right" }}>
                {value}
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="dim" style={{ fontSize: "0.75rem", margin: "0.75rem 0 0" }}>
        Rubric v{score.rubric_version}.{" "}
        <button
          onClick={() => setShowContributors(!showContributors)}
          style={{
            background: "none", border: "none", color: "var(--accent)",
            cursor: "pointer", padding: 0, font: "inherit", textDecoration: "underline",
          }}
        >
          {showContributors ? "Hide" : "What drives this number?"}
        </button>
      </p>

      {showContributors && (
        <div style={{ marginTop: "0.5rem" }}>
          {score.contributing.slice(0, 8).map((c) => (
            <div
              key={c.finding_id}
              className="status-row"
              style={{ justifyContent: "space-between", fontSize: "0.8rem", padding: "0.15rem 0" }}
            >
              <button
                onClick={() =>
                  document
                    .getElementById(`finding-${c.finding_id}`)
                    ?.scrollIntoView({ behavior: "smooth", block: "center" })
                }
                style={{
                  background: "none", border: "none", color: "var(--text)",
                  cursor: "pointer", padding: 0, font: "inherit", textAlign: "left",
                }}
                title="Jump to this finding"
              >
                {c.reason}
              </button>
              <span className="dim">+{c.points.toFixed(1)}</span>
            </div>
          ))}
          {score.contributing.length === 0 && (
            <p className="dim" style={{ fontSize: "0.8rem", margin: 0 }}>
              Nothing counts toward your score yet.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
