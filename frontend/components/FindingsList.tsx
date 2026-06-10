"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Finding, FindingsPage } from "@/lib/api";
import StepUpModal from "@/components/StepUpModal";

const CATEGORY_LABELS: Record<string, string> = {
  credential: "Breached credentials",
  broker: "Data-broker listings",
  social: "Public web & social",
  records: "Public records",
  linkage: "Cross-source linkage",
};

const SENSITIVITY_COLOR: Record<Finding["sensitivity"], string> = {
  critical: "var(--down)",
  high: "var(--warn)",
  medium: "var(--accent)",
  low: "var(--text-dim)",
};

export default function FindingsList({ scanId }: { scanId: string }) {
  const [page, setPage] = useState<FindingsPage | null>(null);
  const [stepUpToken, setStepUpToken] = useState<string | null>(null);
  const [showStepUp, setShowStepUp] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(
    (token?: string | null) => {
      api<FindingsPage>(`/scans/${scanId}/findings`, {
        headers: token ? { "X-Ayin-Step-Up": token } : undefined,
      })
        .then(setPage)
        .catch(() => {});
    },
    [scanId]
  );

  useEffect(() => {
    load(stepUpToken);
  }, [load, stepUpToken]);

  if (!page) return <p className="dim">Loading findings…</p>;
  if (page.findings.length === 0)
    return (
      <div className="card">
        <p style={{ margin: 0 }}>
          Nothing found from the enabled sources — a quiet footprint is a good result.
          As more sources come online, re-scan to keep this picture current.
        </p>
      </div>
    );

  const groups = new Map<string, Finding[]>();
  for (const f of page.findings) {
    groups.set(f.category, [...(groups.get(f.category) ?? []), f]);
  }

  return (
    <div>
      {page.locked_credential_findings > 0 && (
        <div className="card" style={{ borderColor: "var(--warn)" }}>
          <p style={{ margin: 0 }}>
            🔒 {page.locked_credential_findings} credential finding
            {page.locked_credential_findings > 1 ? "s are" : " is"} locked.{" "}
            <button
              onClick={() => setShowStepUp(true)}
              style={{
                background: "none", border: "none", color: "var(--accent)",
                cursor: "pointer", padding: 0, font: "inherit", textDecoration: "underline",
              }}
            >
              Re-enter your password to unlock
            </button>
            .
          </p>
        </div>
      )}

      {[...groups.entries()].map(([category, findings]) => (
        <div className="card" key={category}>
          <h3 style={{ marginTop: 0, fontSize: "0.95rem" }}>
            {CATEGORY_LABELS[category] ?? category}{" "}
            <span className="dim">({findings.length})</span>
          </h3>
          {findings.map((f) => (
            <div
              key={f.id}
              style={{ borderTop: "1px solid var(--border)", padding: "0.6rem 0" }}
            >
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "baseline" }}>
                <span
                  className="dot"
                  style={{ background: SENSITIVITY_COLOR[f.sensitivity], flexShrink: 0 }}
                  title={`sensitivity: ${f.sensitivity}`}
                />
                <div>
                  <p style={{ margin: 0 }}>{f.summary}</p>
                  <p className="dim" style={{ margin: "0.2rem 0 0", fontSize: "0.8rem" }}>
                    {f.source_name} · confidence {(f.confidence * 100).toFixed(0)}% ·
                    captured {new Date(f.captured_at).toLocaleDateString()}
                    {f.source_url && (
                      <>
                        {" · "}
                        <a href={f.source_url} target="_blank" rel="noreferrer noopener">
                          source ↗
                        </a>
                      </>
                    )}
                    {Boolean(f.payload.namesake_risk) && (
                      <> · <span title="Matched by name — could be a namesake. Confirm/reject coming in M2.">may be a namesake</span></>
                    )}
                  </p>
                  {f.category === "broker" && f.payload.removable === true && (
                    <div style={{ marginTop: "0.4rem" }}>
                      <button
                        onClick={() => setExpanded(expanded === f.id ? null : f.id)}
                        style={{
                          background: "none", border: "1px solid var(--border)",
                          color: "var(--accent)", borderRadius: 6, cursor: "pointer",
                          padding: "0.2rem 0.6rem", fontSize: "0.8rem",
                        }}
                      >
                        {expanded === f.id ? "Hide removal steps" : "How to remove this"}
                      </button>
                      {expanded === f.id && (
                        <div
                          style={{
                            marginTop: "0.5rem", padding: "0.6rem 0.8rem",
                            background: "var(--bg)", borderRadius: 8, fontSize: "0.85rem",
                          }}
                        >
                          <p style={{ marginTop: 0 }}>
                            {String(f.payload.opt_out_instructions ?? "")}
                          </p>
                          <p style={{ marginBottom: 0 }}>
                            <a
                              href={String(f.payload.opt_out_url ?? "#")}
                              target="_blank"
                              rel="noreferrer noopener"
                            >
                              Open the opt-out page ↗
                            </a>{" "}
                            <span className="dim">
                              · typical processing: {String(f.payload.expected_processing ?? "varies")}
                            </span>
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                  {f.category === "credential" && !f.step_up_required && (
                    <p className="dim" style={{ margin: "0.3rem 0 0", fontSize: "0.8rem" }}>
                      Exposed data classes:{" "}
                      {(f.payload.data_classes as string[] | undefined)?.join(", ") ?? "—"}
                      {" — "}rotate this password anywhere it was reused and enable MFA.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}

      {showStepUp && (
        <StepUpModal
          onToken={(t) => setStepUpToken(t)}
          onClose={() => setShowStepUp(false)}
        />
      )}
    </div>
  );
}
