"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";

type State = "idle" | "working" | "done" | "error";

function RevokeInner() {
  const token = useSearchParams().get("token");
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function revoke() {
    if (!token) {
      setState("error");
      setMessage("This revoke link is missing its token.");
      return;
    }
    setState("working");
    try {
      await api(`/consent/revoke/${token}`, { method: "POST" });
      setState("done");
    } catch (err) {
      setState("error");
      setMessage(
        err instanceof ApiError && err.status === 404
          ? "This revoke link is invalid or already used."
          : "Could not revoke right now — please try again."
      );
    }
  }

  if (state === "done") {
    return (
      <main>
        <h1>Consent revoked</h1>
        <div className="card">
          <p style={{ margin: 0 }}>
            Done — your authorization has been withdrawn, effective immediately. No
            further scans will run, and nothing more about you will be collected.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main>
      <h1>Revoke consent</h1>
      <div className="card">
        <p style={{ marginTop: 0 }}>
          This withdraws the permission you gave for an Ayin scan of your public
          footprint. It takes effect immediately and can't be undone (a new request
          would be needed to re-authorize).
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button onClick={revoke} disabled={state === "working"} style={dangerButton}>
            {state === "working" ? "Revoking…" : "Revoke my consent"}
          </button>
          <Link href="/" style={{ alignSelf: "center" }} className="dim">
            Cancel
          </Link>
        </div>
        {message && <p style={{ color: "var(--sev-critical)", marginBottom: 0 }}>{message}</p>}
      </div>
    </main>
  );
}

export default function RevokePage() {
  return (
    <Suspense>
      <RevokeInner />
    </Suspense>
  );
}

const dangerButton: React.CSSProperties = {
  padding: "0.55rem 1.2rem",
  background: "var(--sev-critical)",
  color: "#fff",
  border: "none",
  borderRadius: "var(--r-md)",
  fontWeight: 650,
  cursor: "pointer",
};
