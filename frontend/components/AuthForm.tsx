"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, User } from "@/lib/api";

export default function AuthForm({ mode }: { mode: "signup" | "login" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api<User>(`/auth/${mode}`, { method: "POST", body: { email, password } });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card" style={{ display: "grid", gap: "0.75rem" }}>
      <label>
        Email
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={inputStyle}
        />
      </label>
      <label>
        Password {mode === "signup" && <span className="dim">(10+ characters)</span>}
        <input
          type="password"
          required
          minLength={mode === "signup" ? 10 : 1}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={inputStyle}
        />
      </label>
      {error && <p style={{ color: "var(--down)", margin: 0 }}>{error}</p>}
      <button type="submit" disabled={busy} style={buttonStyle}>
        {busy ? "…" : mode === "signup" ? "Create account" : "Log in"}
      </button>
    </form>
  );
}

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  marginTop: "0.25rem",
  padding: "0.5rem 0.75rem",
  background: "var(--bg)",
  color: "var(--text)",
  border: "1px solid var(--border)",
  borderRadius: 8,
};

const buttonStyle: React.CSSProperties = {
  padding: "0.6rem 1rem",
  background: "var(--accent)",
  color: "#06222e",
  border: "none",
  borderRadius: 8,
  fontWeight: 600,
  cursor: "pointer",
};
