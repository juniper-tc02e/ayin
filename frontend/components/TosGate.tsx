"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type TosStatus = { current_version: string; accepted_current: boolean };

export default function TosGate() {
  const [status, setStatus] = useState<TosStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<TosStatus>("/tos").then(setStatus).catch(() => {});
  }, []);

  if (!status || status.accepted_current) return null;

  async function accept() {
    if (!status) return;
    setError(null);
    try {
      const updated = await api<TosStatus>("/tos/accept", {
        method: "POST",
        body: { version: status.current_version },
      });
      setStatus(updated);
    } catch {
      setError("Could not record acceptance — try again.");
    }
  }

  return (
    <div className="card" style={{ borderColor: "var(--warn)" }}>
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Before you can scan</h2>
      <p className="dim" style={{ marginTop: 0 }}>
        Review the <Link href="/terms">Terms of Service &amp; Acceptable Use Policy</Link>{" "}
        (version {status.current_version}). The core of it: Ayin scans <strong>you</strong>,
        never anyone else.
      </p>
      <button
        onClick={accept}
        style={{
          padding: "0.5rem 1rem",
          background: "var(--accent)",
          color: "#06222e",
          border: "none",
          borderRadius: 8,
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        I agree to version {status.current_version}
      </button>
      {error && <p style={{ color: "var(--down)", marginBottom: 0 }}>{error}</p>}
    </div>
  );
}
