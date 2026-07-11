"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";

export default function ExcludePage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ message: string }>("/exclusions/request", {
        method: "POST",
        body: { kind: "email", value: email },
      });
      setMessage(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Exclude me from Ayin</h1>
      <p className="dim">
        Don&apos;t want Ayin to scan you — ever, for anyone? Enter your email address and
        confirm via the link we send. The exclusion is permanent, also removes any existing
        scan data tied to the address, and is honored even if you later create an account.
        No Ayin account needed. We store only a one-way hash of the address.
      </p>
      {message ? (
        <div className="card"><p style={{ margin: 0 }}>{message}</p></div>
      ) : (
        <form onSubmit={submit} className="card" style={{ display: "grid", gap: "0.75rem" }}>
          <div className="field">
            <label htmlFor="exclude-email">Email address</label>
            <input
              id="exclude-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          {error && <p style={{ color: "var(--sev-critical)", margin: 0 }}>{error}</p>}
          <button type="submit" disabled={busy} className="btn btn-primary">
            {busy ? "…" : "Send confirmation link"}
          </button>
          <p className="dim" style={{ margin: 0, fontSize: "0.8rem" }}>
            Phone numbers and other identifiers: email privacy@superayin.com for now.
          </p>
        </form>
      )}
    </main>
  );
}
