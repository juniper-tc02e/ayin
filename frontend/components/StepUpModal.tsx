"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";

export default function StepUpModal({
  onToken,
  onClose,
}: {
  onToken: (token: string) => void;
  onClose: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ step_up_token: string }>("/auth/step-up", {
        method: "POST",
        body: { password },
      });
      onToken(res.step_up_token);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50,
      }}
      onClick={onClose}
    >
      <form
        onSubmit={submit}
        className="card"
        style={{ maxWidth: 380, width: "90%", margin: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Confirm it&apos;s you</h2>
        <p className="dim" style={{ fontSize: "0.9rem" }}>
          Credential-exposure details are extra sensitive, so we ask for your password
          again before showing them. The unlock lasts a few minutes and is logged to
          your audit trail.
        </p>
        <input
          type="password"
          autoFocus
          required
          placeholder="Your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{
            display: "block", width: "100%", padding: "0.5rem 0.75rem",
            background: "var(--bg)", color: "var(--text)",
            border: "1px solid var(--border)", borderRadius: 8, marginBottom: "0.75rem",
          }}
        />
        {error && <p style={{ color: "var(--down)", marginTop: 0 }}>{error}</p>}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            type="submit"
            disabled={busy}
            style={{
              padding: "0.5rem 1rem", background: "var(--accent)", color: "#06222e",
              border: "none", borderRadius: 8, fontWeight: 600, cursor: "pointer",
            }}
          >
            {busy ? "…" : "Unlock details"}
          </button>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "0.5rem 1rem", background: "transparent", color: "var(--text-dim)",
              border: "1px solid var(--border)", borderRadius: 8, cursor: "pointer",
            }}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
