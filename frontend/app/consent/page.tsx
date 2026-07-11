"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError, ConsentAsk } from "@/lib/api";

type Outcome = "granted" | "declined" | null;

function ConsentInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [ask, setAsk] = useState<ConsentAsk | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [adult, setAdult] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome>(null);

  useEffect(() => {
    if (!token) {
      setLoadError("This consent link is missing its token.");
      return;
    }
    api<ConsentAsk>(`/consent/requests/${token}`)
      .then(setAsk)
      .catch((err) =>
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? "This consent link is invalid, already used, or expired."
            : "Could not load this consent request."
        )
      );
  }, [token]);

  async function accept() {
    setBusy(true);
    setActionError(null);
    try {
      await api(`/consent/requests/${token}/accept`, {
        method: "POST",
        body: { adult_attested: adult },
      });
      setOutcome("granted");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not record your consent.");
    } finally {
      setBusy(false);
    }
  }

  async function decline() {
    setBusy(true);
    setActionError(null);
    try {
      await api(`/consent/requests/${token}/decline`, { method: "POST" });
      setOutcome("declined");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not record your decision.");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <main>
        <h1>Consent request</h1>
        <div className="card">
          <p style={{ margin: 0 }}>{loadError}</p>
        </div>
        <p className="dim" style={{ marginTop: "1rem" }}>
          <Link href="/">Return home</Link>
        </p>
      </main>
    );
  }

  if (outcome === "granted") {
    return (
      <main>
        <h1>Consent granted</h1>
        <div className="card">
          <p style={{ margin: 0 }}>
            Thank you — you’ve authorized this scan. It’s time-bound, and we’ve emailed you
            a confirmation with a one-click <strong>revoke link</strong> — use it any time to
            withdraw, no account needed. Nothing beyond what you authorized will be scanned.
          </p>
        </div>
      </main>
    );
  }
  if (outcome === "declined") {
    return (
      <main>
        <h1>Request declined</h1>
        <div className="card">
          <p style={{ margin: 0 }}>
            You’ve declined. No scan will run, and nothing about you will be collected.
          </p>
        </div>
      </main>
    );
  }

  if (!ask) return <main><p className="dim">Loading…</p></main>;

  return (
    <main>
      <h1>A scan needs your consent</h1>
      <div className="card">
        <p style={{ marginTop: 0 }}>
          <strong>{ask.requester_email}</strong> is asking your permission to run an Ayin
          exposure scan of your <strong>public footprint</strong> — the same self-scan
          Ayin offers you, run on your behalf.
        </p>
        <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.4rem 1rem", margin: 0 }}>
          <dt className="dim">Purpose</dt>
          <dd style={{ margin: 0 }}>{ask.purpose}</dd>
          <dt className="dim">Your email</dt>
          <dd style={{ margin: 0 }}>{ask.subject_email}</dd>
          {ask.usernames.length > 0 && (
            <>
              <dt className="dim">Handles</dt>
              <dd style={{ margin: 0 }}>{ask.usernames.join(", ")}</dd>
            </>
          )}
          <dt className="dim">Valid for</dt>
          <dd style={{ margin: 0 }}>{ask.ttl_days} days (revocable any time)</dd>
        </dl>
      </div>

      <div className="card">
        <p style={{ marginTop: 0, fontSize: "0.9rem", color: "var(--sev-high)" }}>
          ⚠️ Only authorize if you recognize <strong>{ask.requester_email}</strong> and were
          expecting this request. Ayin only reads <strong>publicly available</strong> sources
          — never private accounts — and you can withdraw consent whenever you like. If you
          don’t recognize this request, choose Decline — nothing about you will be scanned.
        </p>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start", margin: "0.5rem 0 1rem" }}>
          <input
            type="checkbox"
            checked={adult}
            onChange={(e) => setAdult(e.target.checked)}
            style={{ marginTop: "0.2rem" }}
          />
          <span>I confirm I am 18 or older and I authorize this scan of my public footprint.</span>
        </label>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button onClick={accept} disabled={!adult || busy} className="btn btn-primary">
            {busy ? "…" : "Authorize this scan"}
          </button>
          <button onClick={decline} disabled={busy} className="btn btn-ghost">
            Decline
          </button>
        </div>
        {actionError && <p style={{ color: "var(--sev-critical)", marginBottom: 0 }}>{actionError}</p>}
        <p className="dim" style={{ marginTop: "0.75rem", marginBottom: 0, fontSize: "0.8rem" }}>
          <a
            href="mailto:abuse@superayin.com?subject=Consent%20request%20abuse%20report"
            style={{ color: "inherit" }}
          >
            Report this request as abuse
          </a>
        </p>
      </div>
    </main>
  );
}

export default function ConsentPage() {
  return (
    <Suspense>
      <ConsentInner />
    </Suspense>
  );
}
