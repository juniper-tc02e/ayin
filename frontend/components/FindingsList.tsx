"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Finding, FindingsPage, LlmOpinion } from "@/lib/api";
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

export default function FindingsList({
  scanId,
  onReviewed,
}: {
  scanId: string;
  onReviewed?: () => void;
}) {
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

  async function review(findingId: string, action: "confirm" | "reject") {
    try {
      await api(`/findings/${findingId}/${action}`, { method: "POST" });
      load(stepUpToken);
      onReviewed?.();
    } catch {
      /* surface-level errors are non-fatal here */
    }
  }

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

  const possible = page.findings.filter((f) => f.match_status === "possible");
  const rejected = page.findings.filter((f) => f.match_status === "rejected");
  const counted = page.findings.filter(
    (f) => f.match_status === "auto_matched" || f.match_status === "confirmed"
  );
  const groups = new Map<string, Finding[]>();
  for (const f of counted) {
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
              id={`finding-${f.id}`}
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
                    {f.corroboration_count > 1 && (
                      <> · seen by {f.corroboration_count} sources</>
                    )}
                    {f.match_status === "confirmed" && (
                      <> · <span style={{ color: "var(--ok)" }}>confirmed by you</span></>
                    )}
                  </p>
                  {f.conflicts.length > 0 && (
                    <p style={{ margin: "0.3rem 0 0", fontSize: "0.8rem", color: "var(--warn)" }}>
                      ⚠ Sources disagree on{" "}
                      {f.conflicts.map((c) => c.field).join(", ")} — shown as reported, not
                      merged.
                    </p>
                  )}
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

      {possible.length > 0 && (
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <h3 style={{ marginTop: 0, fontSize: "0.95rem" }}>
            Possible matches — is this you? <span className="dim">({possible.length})</span>
          </h3>
          <p className="dim" style={{ marginTop: 0, fontSize: "0.85rem" }}>
            These were found via your name or username, which others can share. They
            don&apos;t count toward your score unless you confirm them.
          </p>
          {possible.map((f) => (
            <div
              key={f.id}
              id={`finding-${f.id}`}
              style={{ borderTop: "1px solid var(--border)", padding: "0.6rem 0" }}
            >
              <p style={{ margin: 0 }}>{f.summary}</p>
              <p className="dim" style={{ margin: "0.2rem 0 0.4rem", fontSize: "0.8rem" }}>
                {f.source_name} · match confidence{" "}
                {f.match_confidence != null ? `${Math.round(f.match_confidence * 100)}%` : "—"}
                {f.source_url && (
                  <>
                    {" · "}
                    <a href={f.source_url} target="_blank" rel="noreferrer noopener">
                      view source ↗
                    </a>
                  </>
                )}
              </p>
              {f.llm_opinion && <ERAdvice opinion={f.llm_opinion} />}
              <span style={{ display: "flex", gap: "0.5rem" }}>
                <button style={reviewButton("var(--ok)")} onClick={() => review(f.id, "confirm")}>
                  Yes, that&apos;s me
                </button>
                <button style={reviewButton("var(--down)")} onClick={() => review(f.id, "reject")}>
                  Not me
                </button>
              </span>
            </div>
          ))}
        </div>
      )}

      {rejected.length > 0 && (
        <p className="dim" style={{ fontSize: "0.8rem" }}>
          {rejected.length} finding{rejected.length > 1 ? "s" : ""} marked &quot;not me&quot; —
          excluded from your score.
        </p>
      )}

      {showStepUp && (
        <StepUpModal
          onToken={(t) => setStepUpToken(t)}
          onClose={() => setShowStepUp(false)}
        />
      )}
    </div>
  );
}

function reviewButton(color: string): React.CSSProperties {
  return {
    padding: "0.3rem 0.8rem",
    background: "transparent",
    color,
    border: "1px solid var(--border)",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: "0.85rem",
  };
}

// Plain-language read of Qwen's verdict — never a directive. The leaning
// only tints a small dot; the words stay "leans …" so nothing reads as a
// decision the user must accept. Colors avoid the product's good/bad
// semantics (esp. --ok, the confirm-button green) so no lean looks like the
// "recommended" answer: match = cautionary amber (a confirmed match raises
// exposure), no_match = neutral accent, unsure = dim.
const ER_VERDICT: Record<LlmOpinion["verdict"], { label: string; color: string }> = {
  match: { label: "leans toward this being you", color: "var(--warn)" },
  no_match: { label: "leans toward this NOT being you", color: "var(--accent)" },
  unsure: { label: "isn't sure", color: "var(--text-dim)" },
};

// Defensive display cap on the model-written evidence list (the API allows
// up to 20); disclosed, not silent — matches the house convention.
const EVIDENCE_SHOWN = 5;

/**
 * B4 gray-zone second opinion (E4). Advice ONLY — the user's Yes/No below
 * is the decision (FR-ER-1), so this reads as a hint, never a verdict:
 * subdued styling (a quiet ✦ Qwen mark, not the E2/E3 accent pill, so it
 * never competes with the decision), "leans"/"isn't sure" wording, an
 * explicit "your answer decides" line. Evidence bullets are model output —
 * rendered strictly as text (already control-char-stripped server-side).
 */
function ERAdvice({ opinion }: { opinion: LlmOpinion }) {
  const v = ER_VERDICT[opinion.verdict] ?? ER_VERDICT.unsure;
  const extra = opinion.evidence.length - EVIDENCE_SHOWN;
  return (
    <div
      style={{
        margin: "0 0 0.5rem",
        padding: "0.5rem 0.7rem",
        background: "var(--bg)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        fontSize: "0.8rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
        <span
          className="dot"
          style={{ background: v.color, flexShrink: 0 }}
          aria-hidden
        />
        <span>
          <span style={{ color: "var(--accent)" }}>✦ Qwen</span>
          <span className="dim">&apos;s hint — </span>
          {v.label}
        </span>
      </div>
      {opinion.evidence.length > 0 && (
        <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.2rem" }}>
          {opinion.evidence.slice(0, EVIDENCE_SHOWN).map((e, i) => (
            <li key={i} className="dim" style={{ marginBottom: "0.15rem" }}>
              {e}
            </li>
          ))}
        </ul>
      )}
      {extra > 0 && (
        <p
          className="dim"
          style={{ margin: "0.2rem 0 0", paddingLeft: "1.2rem", fontSize: "0.75rem" }}
        >
          …and {extra} more
        </p>
      )}
      <p className="dim" style={{ margin: "0.35rem 0 0", fontSize: "0.72rem" }}>
        Only a hint — your answer below decides.
        {opinion.model ? `  ·  ${opinion.model}` : ""}
      </p>
    </div>
  );
}
