"use client";

import { useEffect, useMemo, useState } from "react";
import { api, CategorySummary, NarrativeClaim, ReportData, ReportNarrative } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  credential: "Breached credentials",
  broker: "Data-broker listings",
  social: "Public web & social",
  records: "Public records",
  linkage: "Cross-source linkage",
};

// Defensive display caps — the API allows up to 500 claims / 50 summaries; a
// normal scan has a handful. Anything beyond reads better in the findings
// list itself.
const CLAIMS_SHOWN = 12;
const SUMMARIES_SHOWN = 8;

/** Claims render only for LLM-written narratives: the template path copies
 * each finding's summary verbatim, which would word-for-word duplicate the
 * findings list below — the template's aggregate sections stand alone. */
function visibleClaims(n: ReportNarrative): NarrativeClaim[] {
  return n.generated_by === "qwen" ? n.claims.slice(0, CLAIMS_SHOWN) : [];
}

/** Only known categories render: `category` is model-written, and an unknown
 * value must never appear styled as the app's own label. */
function visibleSummaries(n: ReportNarrative): CategorySummary[] {
  return n.category_summaries
    .filter((s) => CATEGORY_LABELS[s.category] !== undefined)
    .slice(0, SUMMARIES_SHOWN);
}

function rendersAnything(n: ReportNarrative): boolean {
  return (
    visibleClaims(n).length + n.top_fixes.length + visibleSummaries(n).length > 0
  );
}

/**
 * Grounded report narrative (B1/E2): plain-language statements written by
 * Qwen (or the deterministic template when the LLM is off), every statement
 * citing the finding id(s) it rests on — tap a citation number to jump to
 * the source finding.
 *
 * Deliberately NOT rendered here: the verdict line. The backend pins the
 * narrative verdict to the same deterministic scoring verdict ScorePanel
 * already shows, so repeating it would only duplicate.
 *
 * Claim text is model output — render strictly as text, never markup.
 */
export default function NarrativePanel({
  scanId,
  refreshKey,
  onLoaded,
}: {
  scanId: string;
  refreshKey: number;
  // Lets the page hand the "top fixes" slot to this card when the narrative
  // provides one (instead of rendering the checklist top-3 twice in a row).
  onLoaded?: (info: { hasTopFixes: boolean }) => void;
}) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [failed, setFailed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    // Stale-response guard: /report can regenerate synchronously (an LLM
    // round-trip taking seconds), so overlapping requests are normal here —
    // only the latest request may touch state, or an out-of-order response
    // could install an old narrative against a newer score.
    let stale = false;
    setRefreshing(true);
    api<ReportData>(`/scans/${scanId}/report`)
      .then((r) => {
        if (stale) return;
        setReport(r);
        setRefreshing(false);
        onLoaded?.({
          hasTopFixes: rendersAnything(r.narrative) && r.narrative.top_fixes.length > 0,
        });
      })
      .catch(() => {
        if (stale) return;
        // keep any previous narrative visible — fail soft, never blank
        setFailed(true);
        setRefreshing(false);
      });
    return () => {
      stale = true;
    };
    // onLoaded intentionally not a dep: page passes an inline setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanId, refreshKey]);

  const narrative: ReportNarrative | null = report?.narrative ?? null;

  const shown = useMemo(
    () =>
      narrative
        ? {
            claims: visibleClaims(narrative),
            summaries: visibleSummaries(narrative),
          }
        : { claims: [], summaries: [] },
    [narrative]
  );

  // One stable citation number per distinct finding across everything
  // actually rendered, in order of first appearance.
  const citationOrder = useMemo(() => {
    const order: string[] = [];
    if (narrative) {
      for (const c of [...shown.claims, ...narrative.top_fixes, ...shown.summaries])
        for (const id of c.finding_ids) if (!order.includes(id)) order.push(id);
    }
    return order;
  }, [narrative, shown]);

  // First load: the very first /report hit may generate synchronously when
  // the finalize-time pre-generation was skipped — say so instead of nothing.
  if (!narrative)
    return failed ? (
      <p className="dim" role="status" style={{ fontSize: "0.85rem", marginTop: "1rem" }}>
        Couldn't load the summary — the findings below are still accurate.
      </p>
    ) : (
      <p className="dim" style={{ fontSize: "0.85rem", marginTop: "1rem" }}>
        Writing your report…
      </p>
    );

  if (!rendersAnything(narrative)) return null; // zero findings: the low-exposure card says it better

  return (
    // card--glow: the cited AI narrative is the product's signature surface —
    // it gets the escalated chrome, not the same box as everything else.
    <div className="card card--glow">
      <div
        style={{
          display: "flex", justifyContent: "space-between",
          alignItems: "baseline", gap: "0.75rem", flexWrap: "wrap",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "1.05rem" }}>
          What this means
          {refreshing && (
            <span className="dim" style={{ fontSize: "0.75rem", fontWeight: 400, marginLeft: "0.5rem" }}>
              updating…
            </span>
          )}
        </h2>
        {narrative.generated_by === "qwen" ? (
          <span
            title="Written by Qwen from your scan's findings — the citation guard rejects any statement that doesn't trace to a real finding."
            style={{
              fontSize: "0.7rem", color: "var(--accent)",
              border: "1px solid var(--accent)", borderRadius: 999,
              padding: "0.05rem 0.55rem", whiteSpace: "nowrap",
            }}
          >
            ✦ written by Qwen{narrative.model ? ` · ${narrative.model}` : ""}
          </span>
        ) : (
          <span className="dim" style={{ fontSize: "0.7rem" }}>
            standard summary
          </span>
        )}
      </div>

      {shown.claims.map((c, i) => (
        <p key={i} style={{ margin: "0.6rem 0 0" }}>
          {c.text} <Cites ids={c.finding_ids} order={citationOrder} />
        </p>
      ))}
      {narrative.generated_by === "qwen" && narrative.claims.length > CLAIMS_SHOWN && (
        <p className="dim" style={{ margin: "0.4rem 0 0", fontSize: "0.8rem" }}>
          …and {narrative.claims.length - CLAIMS_SHOWN} more — the findings they
          cite are all listed below.
        </p>
      )}

      {narrative.top_fixes.length > 0 && (
        <>
          <h3
            className="dim"
            style={{
              fontSize: "0.75rem", textTransform: "uppercase",
              letterSpacing: "0.06em", margin: "1rem 0 0.25rem", fontWeight: 600,
            }}
          >
            Where to start
          </h3>
          <ol style={{ margin: 0, paddingLeft: "1.25rem" }}>
            {narrative.top_fixes.map((f, i) => (
              <li key={i} style={{ margin: "0.25rem 0" }}>
                {f.text} <Cites ids={f.finding_ids} order={citationOrder} />
              </li>
            ))}
          </ol>
        </>
      )}

      {shown.summaries.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          {shown.summaries.map((s, i) => (
            <p key={i} className="dim" style={{ margin: "0.2rem 0", fontSize: "0.8rem" }}>
              <strong>{CATEGORY_LABELS[s.category]}:</strong>{" "}
              {s.text} <Cites ids={s.finding_ids} order={citationOrder} />
            </p>
          ))}
        </div>
      )}

      <p className="dim" style={{ fontSize: "0.75rem", margin: "1rem 0 0" }}>
        Every statement above cites the finding it rests on — tap a number to
        see the source. This text describes the exposure of your{" "}
        <em>data</em> only; it never judges you.
      </p>
    </div>
  );
}

/** Numbered citation chips → scroll to the source finding's card. */
function Cites({ ids, order }: { ids: string[]; order: string[] }) {
  // dedupe: finding_ids is model output and may repeat an id
  const unique = [...new Set(ids)];
  if (unique.length === 0) return null;
  return (
    <span>
      {unique.map((id) => (
        <button
          key={id}
          onClick={() =>
            document
              .getElementById(`finding-${id}`)
              ?.scrollIntoView({ behavior: "smooth", block: "center" })
          }
          title="Jump to the source finding"
          style={{
            background: "none", border: "1px solid var(--border)",
            color: "var(--accent)", borderRadius: 6, cursor: "pointer",
            padding: "0 0.35rem", marginLeft: "0.25rem", fontSize: "0.7rem",
            verticalAlign: "text-top", lineHeight: 1.4,
          }}
        >
          {order.indexOf(id) + 1}
        </button>
      ))}
    </span>
  );
}
