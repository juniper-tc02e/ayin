"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, AccountSummary, ApiError } from "@/lib/api";

export default function DataRights() {
  const router = useRouter();
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [ack, setAck] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<AccountSummary>("/account/summary").then(setSummary).catch(() => {});
  }, []);

  async function deleteEverything(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/account/delete", { method: "POST", body: { password } });
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Your data &amp; rights</h2>
      {summary && (
        <p className="dim" style={{ fontSize: "0.85rem", marginTop: 0 }}>
          Ayin currently holds: {summary.identifiers} identifier(s), {summary.scans} scan(s),{" "}
          {summary.findings} finding(s), {summary.vault_items} encrypted item(s) (auto-expire
          in {summary.pii_retention_days} days). {summary.note}
        </p>
      )}
      <p style={{ fontSize: "0.9rem" }}>
        <Link href="/exclude">Exclude an identifier from Ayin entirely</Link> ·{" "}
        <Link href="/terms">Terms &amp; acceptable use</Link>
      </p>

      {!confirming ? (
        <button
          onClick={() => setConfirming(true)}
          style={{
            padding: "0.45rem 0.9rem", background: "transparent", color: "var(--down)",
            border: "1px solid var(--border)", borderRadius: 8, cursor: "pointer",
          }}
        >
          Delete my account and all data
        </button>
      ) : (
        <form onSubmit={deleteEverything} style={{ display: "grid", gap: "0.5rem", maxWidth: 420 }}>
          <p style={{ margin: 0, fontSize: "0.9rem" }}>
            This crypto-shreds your data and cannot be undone. Type{" "}
            <code>DELETE</code> and your password to confirm.
          </p>
          <input
            aria-label="Type DELETE to confirm"
            placeholder='Type "DELETE"'
            value={ack}
            onChange={(e) => setAck(e.target.value)}
            style={inputStyle}
          />
          <input
            type="password"
            aria-label="Your password"
            placeholder="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={inputStyle}
          />
          {error && <p style={{ color: "var(--down)", margin: 0 }}>{error}</p>}
          <span style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="submit"
              disabled={busy || ack !== "DELETE" || !password}
              style={{
                padding: "0.45rem 0.9rem", background: "var(--down)", color: "#fff",
                border: "none", borderRadius: 8, cursor: "pointer",
                opacity: ack === "DELETE" && password ? 1 : 0.5,
              }}
            >
              {busy ? "…" : "Permanently delete everything"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              style={{
                padding: "0.45rem 0.9rem", background: "transparent",
                color: "var(--text-dim)", border: "1px solid var(--border)",
                borderRadius: 8, cursor: "pointer",
              }}
            >
              Cancel
            </button>
          </span>
        </form>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "0.45rem 0.6rem",
  background: "var(--bg)",
  color: "var(--text)",
  border: "1px solid var(--border)",
  borderRadius: 8,
};
