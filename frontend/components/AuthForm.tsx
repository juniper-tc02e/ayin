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
    <form onSubmit={submit} className="card card--raised" style={{ marginTop: 0 }}>
      <div className="field">
        <label htmlFor="auth-email">Email</label>
        <input
          id="auth-email"
          type="email"
          required
          autoComplete="email"
          aria-describedby={error ? "auth-error" : undefined}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="auth-password">
          Password {mode === "signup" && <span className="dim">(10+ characters)</span>}
        </label>
        <input
          id="auth-password"
          type="password"
          required
          minLength={mode === "signup" ? 10 : 1}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          aria-describedby={error ? "auth-error" : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      {mode === "signup" && inviteRequired && (
        <div className="field">
          <label htmlFor="auth-invite">
            Invite code <span className="dim">(Ayin is in private beta)</span>
          </label>
          <input
            id="auth-invite"
            required
            placeholder="AYIN-XXXX-XXXX"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
          />
        </div>
      )}
      {error && (
        <p id="auth-error" role="alert" style={{ color: "var(--sev-critical)", margin: "0 0 var(--sp-3)" }}>
          {error}
        </p>
      )}
      <button type="submit" disabled={busy} className="btn btn-primary" style={{ width: "100%" }}>
        {busy ? "…" : mode === "signup" ? "Create account" : "Log in"}
      </button>
    </form>
  );
}
