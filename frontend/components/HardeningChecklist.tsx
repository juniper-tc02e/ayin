"use client";

import { useEffect, useState } from "react";
import { api, Checklist, ChecklistItem, trackClient } from "@/lib/api";

export default function HardeningChecklist({
  scanId,
  refreshKey,
  topOnly,
}: {
  scanId: string;
  refreshKey?: number;
  topOnly?: number;
}) {
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [tracked, setTracked] = useState<Set<string>>(new Set());

  useEffect(() => {
    api<Checklist>(`/scans/${scanId}/checklist`).then(setChecklist).catch(() => {});
  }, [scanId, refreshKey]);

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
  open,
  onToggle,
}: {
  item: ChecklistItem;
  index?: number;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{ borderTop: "1px solid var(--border)", padding: "0.6rem 0" }}>
      <div
        style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "0.5rem", cursor: "pointer" }}
        onClick={onToggle}
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
      </div>
      {open && (
        <ol style={{ margin: "0.5rem 0 0", paddingLeft: "1.4rem", fontSize: "0.9rem" }}>
          {item.steps.map((s, i) => (
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
      )}
    </div>
  );
}
