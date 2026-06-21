"use client";

import { useState } from "react";
import { Checklist, ChecklistItem, trackClient } from "@/lib/api";

// Defensive display cap on the model-written step list (the API allows up to
// 30 steps/finding); a real B3 draft has a handful. Matches NarrativePanel's
// convention so model output never visually swamps the deterministic floor.
const STEPS_SHOWN = 10;

/**
 * Read-only hardening checklist. The `checklist` is fetched once by the
 * report page and passed in (both the top-3 and full instances share it) so
 * the B3 generation behind GET /checklist runs at most once per view.
 *
 * Each item shows Qwen-personalized steps (B3) as the primary list when
 * present, with the deterministic playbook steps always reachable beneath —
 * the LLM personalizes, it never replaces the floor (ADR-0003).
 */
export default function HardeningChecklist({
  scanId,
  checklist,
  topOnly,
}: {
  scanId: string;
  checklist: Checklist | null;
  topOnly?: number;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const [tracked, setTracked] = useState<Set<string>>(new Set());

  if (!checklist) return null;
  const items = topOnly ? checklist.items.slice(0, topOnly) : checklist.items;
  if (items.length === 0)
    return topOnly ? null : (
      <div className="card">
        <p style={{ margin: 0 }}>
          Nothing needs fixing right now — your counted exposure is already minimal.
        </p>
      </div>
    );

  return (
    <div className="card" style={topOnly ? { borderColor: "var(--accent)" } : undefined}>
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>
        {topOnly ? "Top things to fix now" : "Your full hardening plan"}
      </h2>
      {topOnly ? (
        <p className="dim" style={{ marginTop: 0, fontSize: "0.85rem" }}>
          Ranked by how much each fix shrinks your score. Start at the top.
        </p>
      ) : null}
      {items.map((item, idx) => (
        <ChecklistRow
          key={item.finding_id}
          item={item}
          index={topOnly ? idx + 1 : undefined}
          anchorId={topOnly ? undefined : `fix-${item.finding_id}`}
          open={open === item.finding_id}
          onToggle={() => {
            const next = open === item.finding_id ? null : item.finding_id;
            setOpen(next);
            if (next && !tracked.has(item.finding_id)) {
              setTracked(new Set(tracked).add(item.finding_id));
              trackClient("action_started", scanId, {
                category: item.category,
                effort: item.effort,
              });
            }
          }}
        />
      ))}
    </div>
  );
}

function ChecklistRow({
  item,
  index,
  anchorId,
  open,
  onToggle,
}: {
  item: ChecklistItem;
  index?: number;
  anchorId?: string;
  open: boolean;
  onToggle: () => void;
}) {
  const personalized = item.personalized_steps ?? [];
  const hasPersonalized = personalized.length > 0;
  // The opt-out link comes from our own connector payload (a deterministic
  // playbook step), never from model output — safe to surface as a link even
  // alongside personalized prose, and it's the highest-value broker CTA.
  const optOutStep = item.steps.find((s) => s.startsWith("Opt-out page: http"));
  // Standard (playbook) steps default to hidden when personalized steps lead,
  // but stay one click away — the floor is always reachable.
  const [showStandard, setShowStandard] = useState(false);

  return (
    <div id={anchorId} style={{ borderTop: "1px solid var(--border)", padding: "0.6rem 0", scrollMarginTop: "80px" }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        style={{
          display: "flex", justifyContent: "space-between", alignItems: "baseline",
          gap: "0.5rem", cursor: "pointer", width: "100%", background: "none",
          border: "none", padding: 0, font: "inherit", color: "inherit", textAlign: "left",
        }}
      >
        <span>
          {index ? <strong>{index}. </strong> : null}
          {item.title}
        </span>
        <span style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
          {item.expected_score_delta > 0 && (
            <code style={{ color: "var(--ok)", fontSize: "0.8rem" }}>
              −{item.expected_score_delta} pts
            </code>
          )}
          <code className="dim" style={{ fontSize: "0.8rem" }}>{item.effort} effort</code>
        </span>
      </button>

      {open &&
        (hasPersonalized ? (
          <div style={{ marginTop: "0.5rem" }}>
            <span
              title="Rewritten for your situation by Qwen from the standard steps — the standard steps below are always available."
              style={{
                fontSize: "0.7rem", color: "var(--accent)",
                border: "1px solid var(--accent)", borderRadius: 999,
                padding: "0.05rem 0.55rem", whiteSpace: "nowrap",
              }}
            >
              ✦ personalized by Qwen
            </span>
            {/* model output — render strictly as text, never linkified */}
            <ol style={{ margin: "0.5rem 0 0", paddingLeft: "1.4rem", fontSize: "0.9rem" }}>
              {personalized.slice(0, STEPS_SHOWN).map((s, i) => (
                <li key={i} style={{ marginBottom: "0.25rem" }}>
                  {s}
                </li>
              ))}
            </ol>
            {personalized.length > STEPS_SHOWN && (
              <p className="dim" style={{ fontSize: "0.8rem", margin: "0.25rem 0 0" }}>
                …and {personalized.length - STEPS_SHOWN} more — see the standard steps below.
              </p>
            )}
            {/* deterministic opt-out link (broker), surfaced without an extra click */}
            {optOutStep && (
              <p style={{ margin: "0.5rem 0 0", fontSize: "0.9rem" }}>
                <a
                  href={optOutStep.replace("Opt-out page: ", "")}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  Open the opt-out page ↗
                </a>
              </p>
            )}
            <button
              onClick={() => setShowStandard((v) => !v)}
              style={{
                background: "none", border: "none", color: "var(--accent)",
                cursor: "pointer", padding: "0.4rem 0 0", font: "inherit",
                fontSize: "0.8rem", textDecoration: "underline",
              }}
            >
              {showStandard ? "Hide the standard steps" : "Show the standard steps"}
            </button>
            {showStandard && <PlaybookSteps steps={item.steps} dim />}
          </div>
        ) : (
          <PlaybookSteps steps={item.steps} />
        ))}
    </div>
  );
}

/** The deterministic playbook steps — the trustworthy floor. Only these
 * render the opt-out link, because the URL comes from our own connector
 * payload, not from model output. */
function PlaybookSteps({ steps, dim }: { steps: string[]; dim?: boolean }) {
  return (
    <ol
      style={{
        margin: dim ? "0.4rem 0 0" : "0.5rem 0 0",
        paddingLeft: "1.4rem",
        fontSize: dim ? "0.85rem" : "0.9rem",
        color: dim ? "var(--text-dim)" : undefined,
      }}
    >
      {steps.map((s, i) => (
        <li key={i} style={{ marginBottom: "0.25rem" }}>
          {s.startsWith("Opt-out page: http") ? (
            <a href={s.replace("Opt-out page: ", "")} target="_blank" rel="noreferrer noopener">
              Open the opt-out page ↗
            </a>
          ) : (
            s
          )}
        </li>
      ))}
    </ol>
  );
}
