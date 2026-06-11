"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, User } from "@/lib/api";

export default function AuthForm({ mode }: { mode: "signup" | "login" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [inviteRequired, setInviteRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (mode === "signup") {
      api<{ beta_invite_required: boolean }>("/config")
        .then((c) => setInviteRequired(c.beta_invite_required))
        .catch(() => {});
    }
  }, [mode]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { email, password };
      if (mode === "signup" && inviteRequired) body.invite_code = inviteCode;
      await api<User>(`/auth/${mode}`, { method: "POST", body });
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
      {mode === "signup" && inviteRequired && (
        <label>
          Invite code <span className="dim">(Ayin is in private beta)</span>
          <input
            required
            placeholder="AYIN-XXXX-XXXX"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
            style={inputStyle}
          />
        </label>
      )}
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
