"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, ActivityEvent, api, ApiError, FindingsPage, Scan } from "@/lib/api";
import FindingsList from "@/components/FindingsList";
import PlannerTrail from "@/components/PlannerTrail";
import ScorePanel from "@/components/ScorePanel";

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  gated: "Safety checks",
  running: "Scanning sources",
  resolving: "Resolving results",
  scoring: "Scoring",
  done: "Complete",
  failed: "Stopped",
  held: "Held for review",
};

const ACTIVE_STATUSES = ["queued", "gated", "running", "resolving", "scoring"];

export default function ScanPanel() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewVersion, setReviewVersion] = useState(0);
  const [partial, setPartial] = useState<FindingsPage | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // last (scan, progress) we fetched partial findings for — so we don't
  // re-read /findings every 2s tick (that endpoint is audited; each read
  // takes the audit hash-chain lock). Fetch only when progress advances.
  const partialSigRef = useRef<string>("");

  const refresh = useCallback(() => {
    api<Scan[]>("/scans")
      .then((rows) => {
        setScans(rows);
        const active = rows.find((s) => ACTIVE_STATUSES.includes(s.status));
        if (active) {
          // Self-start the poll loop whenever a scan is in flight — this also
          // restarts it after a mid-scan page reload (the mount effect calls
          // refresh once; without this the panel would freeze). Only while the
          // tab is visible, so backgrounded tabs don't keep polling.
          if (!pollRef.current && document.visibilityState === "visible") {
            pollRef.current = setInterval(refresh, 2000);
          }
          // Partial results change only as connector jobs finish — fetch on a
          // progress transition, not every tick, to avoid an audited /findings
          // read each poll.
          const sig = `${active.id}:${active.progress.jobs_done}:${active.progress.jobs_failed}`;
          if (sig !== partialSigRef.current) {
            partialSigRef.current = sig;
            api<FindingsPage>(`/scans/${active.id}/findings`).then(setPartial).catch(() => {});
          }
        } else {
          setPartial(null);
          partialSigRef.current = "";
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refresh]);

  // Pause the liveness poll while the tab is hidden (no point auditing reads
  // nobody is watching); resume — and self-restart if a scan is active — on
  // return.
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } else {
        refresh();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [refresh]);

  async function startScan() {
    setBusy(true);
    setError(null);
    try {
      const scan = await api<Scan>("/scans", { method: "POST" });
      setSelected(scan.id);
      refresh(); // self-starts polling when the new scan is still active
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.message.startsWith("no_verified_anchor")) {
          setError("Verify at least one email or phone above before scanning — Ayin only scans what you've proven is yours.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Something went wrong starting the scan.");
      }
    } finally {
      setBusy(false);
    }
  }

  const selectedScan = scans.find((s) => s.id === selected) ?? scans[0];
  const selectedId = selectedScan?.id ?? null;
  // Signature of what the activity feed depends on — fetch /activity only when
  // status or progress actually changes (each read takes the audit hash-chain
  // lock + writes a record), not on every 2s liveness poll.
  const activitySig = selectedScan
    ? `${selectedScan.status}:${selectedScan.progress.jobs_done}:${selectedScan.progress.jobs_failed}`
    : "";
  // Tracks which scan the rendered trail belongs to, so we clear it the moment
  // a different scan is selected (and never show the prior scan's trail under
  // the new one) — but NOT on a same-scan progress transition, which would
  // make the live trail flicker.
  const activityScanRef = useRef<string | null>(null);

  useEffect(() => {
    if (!selectedId) {
      setActivity([]);
      activityScanRef.current = null;
      return;
    }
    if (activityScanRef.current !== selectedId) {
      setActivity([]); // switched scans — drop the old trail before refetch
      activityScanRef.current = selectedId;
    }
    let stale = false;
    api<Activity>(`/scans/${selectedId}/activity`)
      .then((a) => {
        if (!stale) setActivity(a.events);
      })
      .catch(() => {});
    return () => {
      stale = true;
    };
    // activitySig drives the transition-gated refetch; selectedId switches scan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, activitySig]);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Your exposure scan</h2>
        <button
          onClick={startScan}
          disabled={busy}
          style={{
            padding: "0.5rem 1.1rem", background: "var(--accent)", color: "#06222e",
            border: "none", borderRadius: 8, fontWeight: 600, cursor: "pointer",
          }}
        >
          {busy ? "…" : scans.length ? "Re-scan" : "Run my first scan"}
        </button>
      </div>
      <p className="dim" style={{ fontSize: "0.85rem" }}>
        Checks breach exposure, public web presence, and data-broker listings for your
        verified identifiers. Every scan and every access to your data is audited.
      </p>
      {error && <p style={{ color: "var(--warn)" }}>{error}</p>}

      {selectedScan && (
        <div style={{ marginTop: "0.5rem" }}>
          <div className="status-row" style={{ justifyContent: "space-between" }}>
            <span>
              <span
                className={`dot ${
                  selectedScan.status === "done"
                    ? "ok"
                    : selectedScan.status === "failed"
                      ? "down"
                      : "degraded"
                }`}
              />{" "}
              {STATUS_LABEL[selectedScan.status] ?? selectedScan.status}
              {selectedScan.error && (
                <span className="dim"> — {selectedScan.error}</span>
              )}
            </span>
            <span className="dim" style={{ fontSize: "0.85rem" }}>
              {selectedScan.progress.jobs_done}/{selectedScan.progress.jobs_total} sources
            </span>
          </div>
          {selectedScan.jobs.length > 0 && (
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.4rem" }}>
              {selectedScan.jobs.map((j) => (
                <code key={j.connector_id} style={{ fontSize: "0.75rem" }}>
                  {j.connector_id}: {j.status}
                  {j.status === "done" ? ` (${j.findings_count})` : ""}
                </code>
              ))}
            </div>
          )}

          {/* E5: the agent's activity trail — its source-ordering reasoning,
              the gates, and what Qwen wrote, from this scan's audit log */}
          {activity.length > 0 && (
            <div style={{ marginTop: "0.75rem" }}>
              <h3 className="dim" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.06em", margin: 0, fontWeight: 600 }}>
                Agent activity
              </h3>
              <PlannerTrail events={activity} />
            </div>
          )}

          {["running", "resolving", "scoring"].includes(selectedScan.status) && partial && (
            <p className="dim" style={{ fontSize: "0.85rem", margin: "0.5rem 0 0" }}>
              Partial results streaming in: {partial.findings.length} finding
              {partial.findings.length === 1 ? "" : "s"} so far…
            </p>
          )}
          {selectedScan.status === "done" && (
            <div style={{ marginTop: "1rem" }}>
              <p style={{ margin: "0 0 0.75rem" }}>
                <a
                  href={`/report/${selectedScan.id}`}
                  style={{
                    display: "inline-block", padding: "0.5rem 1rem",
                    background: "var(--accent)", color: "#06222e", borderRadius: 8,
                    fontWeight: 600, textDecoration: "none",
                  }}
                >
                  View your full exposure report →
                </a>
              </p>
              <ScorePanel scanId={selectedScan.id} refreshKey={reviewVersion} />
              <FindingsList
                scanId={selectedScan.id}
                onReviewed={() => setReviewVersion((v) => v + 1)}
              />
            </div>
          )}
        </div>
      )}

      {scans.length > 1 && (
        <p className="dim" style={{ fontSize: "0.8rem", marginBottom: 0 }}>
          History:{" "}
          {scans.map((s) => (
            <button
              key={s.id}
              onClick={() => setSelected(s.id)}
              style={{
                background: "none", border: "none", cursor: "pointer", padding: "0 0.3rem",
                color: s.id === (selectedScan?.id ?? "") ? "var(--accent)" : "var(--text-dim)",
                textDecoration: "underline", font: "inherit", fontSize: "0.8rem",
              }}
            >
              {new Date(s.created_at).toLocaleString()}
            </button>
          ))}
        </p>
      )}
    </div>
  );
}
