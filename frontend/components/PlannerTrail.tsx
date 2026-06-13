"use client";

import { useEffect, useState } from "react";
import { Activity, ActivityEvent, api } from "@/lib/api";

// Detail values arrive as unknown (per-event allowlisted server-side). These
// coerce safely for display; everything renders as text, never markup/href.
function asStr(x: unknown): string {
  return typeof x === "string" ? x : x == null ? "" : String(x);
}
function asNum(x: unknown): string {
  return typeof x === "number" ? String(x) : "—";
}

type Tone = "agent" | "llm" | "muted";
type Row = { label: string; sub?: string; tone: Tone };

// Map one audit event to a human-readable timeline row. The planner
// decisions (tone "agent") carry the model's own reasoning — the agentic
// highlight; the *_generated events (tone "llm") show what Qwen wrote and
// what the citation guard decided.
function describe(e: ActivityEvent): Row {
  const d = e.detail ?? {};
  switch (e.event_type) {
    case "scan.created":
      return { label: "Scan requested", tone: "muted" };
    case "scan.gated":
      return { label: "Safety gates checked", tone: "muted" };
    case "scan.started":
      return {
        label: "Scan started",
        sub: Array.isArray(d.connectors)
          ? `sources: ${(d.connectors as unknown[]).map(asStr).join(", ")}`
          : undefined,
        tone: "muted",
      };
    case "scan.planner_decision":
      return {
        label: `Agent chose to run ${asStr(d.connector)}`,
        sub: asStr(d.reasoning) || undefined,
        tone: "agent",
      };
    case "scan.planner_rejected":
      return {
        label: `Agent proposal refused: ${asStr(d.connector)}`,
        sub: asStr(d.reason) || asStr(d.reasoning) || undefined,
        tone: "agent",
      };
    case "scan.planner_fallback":
      return { label: "Agent unavailable — deterministic order used", tone: "agent" };
    case "scan.planner_done":
      // "complete" is the happy path — only surface the reason when it's the
      // interesting case (sources exhausted, or the model stopped early).
      return {
        label:
          d.reason && d.reason !== "complete"
            ? `Planning ended (${asStr(d.reason)})`
            : "Planning complete",
        tone: "agent",
      };
    case "scan.connector_finished":
      return {
        label: `${asStr(d.connector)} finished`,
        sub:
          typeof d.findings === "number"
            ? `${d.findings} finding${d.findings === 1 ? "" : "s"}`
            : undefined,
        tone: "muted",
      };
    case "scan.connector_retry":
      return { label: `${asStr(d.connector)} — retrying`, tone: "muted" };
    case "scan.connector_failed":
      return { label: `${asStr(d.connector)} — failed`, tone: "muted" };
    case "scan.resolved":
      return {
        label: "Matched & deduplicated",
        sub: `${asNum(d.auto_matched)} matched · ${asNum(d.possible)} possible`,
        tone: "muted",
      };
    case "scan.scored":
      return { label: `Exposure scored: ${asNum(d.overall)}`, tone: "muted" };
    case "scan.narrative_generated":
      return d.used_llm
        ? {
            label: `Report written by ${asStr(d.model)}`,
            sub: `citation guard ${d.guard_ok ? "passed" : "failed"} · ${asNum(d.tokens)} tokens`,
            tone: "llm",
          }
        : { label: "Report written (standard template)", tone: "muted" };
    case "scan.remediation_generated":
      return d.used_llm
        ? {
            label: `Fix steps personalized by ${asStr(d.model)}`,
            sub: `${asNum(d.items_generated)}/${asNum(d.items_requested)} findings · ${asNum(d.tokens)} tokens`,
            tone: "llm",
          }
        : { label: "Fix steps (standard playbook)", tone: "muted" };
    case "scan.er_assist_generated":
      return d.used_llm
        ? {
            label: `Match opinions by ${asStr(d.model)}`,
            sub: `${asNum(d.judgments)} judged · ${asNum(d.tokens)} tokens`,
            tone: "llm",
          }
        : { label: "Match opinions (none)", tone: "muted" };
    case "scan.completed":
      return { label: "Scan complete", tone: "muted" };
    case "scan.refused":
      return { label: "Scan refused", sub: asStr(d.reason) || undefined, tone: "muted" };
    case "scan.held":
      return { label: "Held for review", sub: asStr(d.reason) || undefined, tone: "muted" };
    default:
      return { label: e.event_type, tone: "muted" };
  }
}

const TONE_DOT: Record<Tone, string> = {
  agent: "var(--accent)",
  llm: "var(--accent)",
  muted: "var(--text-dim)",
};

/**
 * Presentational timeline of a scan's activity (E5), rendered from E1's
 * allowlisted/redacted audit events. The agent's source-ordering reasoning
 * is the centerpiece; every value is shown as plain text (model reasoning is
 * already control-char-stripped server-side).
 */
export default function PlannerTrail({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) return null;
  return (
    <div style={{ marginTop: "0.5rem" }}>
      {events.map((e) => {
        const r = describe(e);
        return (
          <div
            key={e.id}
            style={{ display: "flex", gap: "0.5rem", padding: "0.2rem 0" }}
          >
            <span
              className="dot"
              style={{ background: TONE_DOT[r.tone], flexShrink: 0, marginTop: "0.45rem" }}
              aria-hidden
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  display: "flex", justifyContent: "space-between",
                  gap: "0.5rem", alignItems: "baseline",
                }}
              >
                <span
                  style={{
                    fontSize: "0.85rem",
                    color: r.tone === "muted" ? "var(--text-dim)" : "var(--text)",
                  }}
                >
                  {r.label}
                </span>
                <span className="dim" style={{ fontSize: "0.7rem", flexShrink: 0 }}>
                  {new Date(e.occurred_at).toLocaleTimeString()}
                </span>
              </div>
              {r.sub && (
                <p
                  style={{
                    margin: "0.1rem 0 0",
                    fontSize: "0.78rem",
                    // the agent's reasoning is the story — show it in full text,
                    // lightly emphasized; everything else stays dim metadata
                    color: r.tone === "agent" ? "var(--text)" : "var(--text-dim)",
                    fontStyle: r.tone === "agent" ? "italic" : "normal",
                  }}
                >
                  {r.sub}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Collapsible "how Ayin ran this scan" card for the report page. Fetches the
 * activity trail lazily on first expand (each read writes a data-access audit
 * record, so we don't fetch unless asked). Fails soft to an empty state.
 */
export function ActivityTrailCard({ scanId }: { scanId: string }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);

  useEffect(() => {
    if (!open || events !== null) return;
    let stale = false;
    api<Activity>(`/scans/${scanId}/activity`)
      .then((a) => {
        if (!stale) setEvents(a.events);
      })
      .catch(() => {
        if (!stale) setEvents([]);
      });
    return () => {
      stale = true;
    };
  }, [open, events, scanId]);

  return (
    <div className="card">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          background: "none", border: "none", color: "var(--text)",
          cursor: "pointer", padding: 0, font: "inherit",
          display: "flex", alignItems: "center", gap: "0.4rem",
        }}
      >
        <span style={{ fontSize: "0.8rem", color: "var(--accent)" }}>{open ? "▾" : "▸"}</span>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>How Ayin ran this scan</h2>
      </button>
      <p className="dim" style={{ fontSize: "0.8rem", margin: "0.4rem 0 0" }}>
        Every step — the agent&apos;s source-ordering decisions, the safety gates, and
        what the AI wrote — straight from this scan&apos;s immutable audit log.{" "}
        <button
          onClick={() => setOpen((v) => !v)}
          style={{
            background: "none", border: "none", color: "var(--accent)",
            cursor: "pointer", padding: 0, font: "inherit", textDecoration: "underline",
          }}
        >
          {open ? "Hide the trail" : "Show the trail"}
        </button>
      </p>
      {open &&
        (events === null ? (
          <p className="dim" style={{ fontSize: "0.85rem", margin: "0.5rem 0 0" }}>
            Loading…
          </p>
        ) : events.length === 0 ? (
          <p className="dim" style={{ fontSize: "0.85rem", margin: "0.5rem 0 0" }}>
            No activity recorded for this scan.
          </p>
        ) : (
          <PlannerTrail events={events} />
        ))}
    </div>
  );
}
