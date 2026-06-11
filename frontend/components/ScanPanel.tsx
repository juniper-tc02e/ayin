"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, Scan } from "@/lib/api";
import FindingsList from "@/components/FindingsList";
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

export default function ScanPanel() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewVersion, setReviewVersion] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    api<Scan[]>("/scans")
      .then((rows) => {
        setScans(rows);
        const active = rows.find((s) =>
          ["queued", "gated", "running", "resolving", "scoring"].includes(s.status)
        );
        if (!active && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
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

  function startPolling() {
    if (!pollRef.current) pollRef.current = setInterval(refresh, 2000);
  }

  async function startScan() {
    setBusy(true);
    setError(null);
    try {
      const scan = await api<Scan>("/scans", { method: "POST" });
      setSelected(scan.id);
      refresh();
      startPolling();
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
