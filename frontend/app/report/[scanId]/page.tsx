"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError, Checklist, Scan, trackClient } from "@/lib/api";
import ScorePanel from "@/components/ScorePanel";
import NarrativePanel from "@/components/NarrativePanel";
import FindingsList from "@/components/FindingsList";
import HardeningChecklist from "@/components/HardeningChecklist";
import DataRights from "@/components/DataRights";
import IntentCTA from "@/components/IntentCTA";

export default function ReportPage({ params }: { params: Promise<{ scanId: string }> }) {
  const { scanId } = use(params);
  const router = useRouter();
  const [scan, setScan] = useState<Scan | null>(null);
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [reviewVersion, setReviewVersion] = useState(0);
  const [missing, setMissing] = useState(false);
  // When the narrative provides cited "top fixes", it owns the top-3 slot —
  // rendering the checklist's top-3 card right below it would repeat the
  // same three actions back-to-back.
  const [narrativeOwnsTopFixes, setNarrativeOwnsTopFixes] = useState(false);

  useEffect(() => {
    api<Scan>(`/scans/${scanId}`)
      .then((s) => {
        setScan(s);
        if (s.status === "done") trackClient("report_viewed", s.id);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.push("/login");
        else setMissing(true);
      });
  }, [scanId, router]);

  useEffect(() => {
    api<Checklist>(`/scans/${scanId}/checklist`).then(setChecklist).catch(() => {});
  }, [scanId, reviewVersion]);

  if (missing)
    return (
      <main>
        <p className="dim">Report not found. <Link href="/dashboard">Back to dashboard</Link></p>
      </main>
    );
  if (!scan) return <main><p className="dim">Loading your report…</p></main>;
  if (scan.status !== "done")
    return (
      <main>
        <h1>Your exposure report</h1>
        <div className="card">
          <p style={{ margin: 0 }}>
            This scan is {scan.status}
            {scan.error ? <span className="dim"> — {scan.error}</span> : null}.{" "}
            <Link href="/dashboard">Watch progress on the dashboard</Link>.
          </p>
        </div>
      </main>
    );

  const lowExposure = checklist !== null && checklist.current_overall < 10;

  return (
    <main>
      <p style={{ margin: "0 0 0.5rem" }}>
        <Link href="/dashboard" className="dim">← Dashboard</Link>
      </p>
      <h1 style={{ marginTop: 0 }}>Your exposure report</h1>
      <p className="dim" style={{ marginTop: "-0.5rem", fontSize: "0.85rem" }}>
        Scanned {scan.finished_at ? new Date(scan.finished_at).toLocaleString() : "—"} ·{" "}
        {scan.source_set.length} source(s) · every finding cites where it came from
      </p>

      {/* 1. Hero score + verdict */}
      <ScorePanel scanId={scanId} refreshKey={reviewVersion} />

      {/* 1b. Grounded narrative — what the numbers mean, every statement
          citing its source finding (B1/E2) */}
      <NarrativePanel
        scanId={scanId}
        refreshKey={reviewVersion}
        onLoaded={({ hasTopFixes }) => setNarrativeOwnsTopFixes(hasTopFixes)}
      />

      {/* low-exposure: reassure, never a blank page */}
      {lowExposure && (
        <div className="card" style={{ borderColor: "var(--ok)" }}>
          <p style={{ margin: 0 }}>
            Good news: across breaches, data brokers, and the public web, the sources we
            checked found very little tied to your verified identifiers. No action needed —
            re-scan after big life events (moves, sign-ups, breaches in the news), and
            consider the small cleanups below if any appear.
          </p>
        </div>
      )}

      {/* 2. Top 3 to fix now — owned by the narrative's "Where to start"
          when it rendered one */}
      {!narrativeOwnsTopFixes && (
        <HardeningChecklist scanId={scanId} refreshKey={reviewVersion} topOnly={3} />
      )}

      {/* 3. Findings by category (+ possible-match review) */}
      <h2 style={{ fontSize: "1.05rem", marginTop: "1.5rem" }}>What we found, by category</h2>
      <FindingsList scanId={scanId} onReviewed={() => setReviewVersion((v) => v + 1)} />

      {/* 4. Full remediation plan */}
      <h2 style={{ fontSize: "1.05rem", marginTop: "1.5rem" }}>Your remediation plan</h2>
      <HardeningChecklist scanId={scanId} refreshKey={reviewVersion} />
      <p className="dim" style={{ fontSize: "0.8rem" }}>
        Checklist is read-only for now — done-tracking and automated broker removal are
        coming.
      </p>

      {/* 5. Watch for changes — intent capture (M4-4) */}
      <IntentCTA
        scanId={scanId}
        hasBrokerFindings={(checklist?.items ?? []).some((i) => i.category === "broker")}
      />

      {/* 6. Your data & rights */}
      <DataRights />
    </main>
  );
}
