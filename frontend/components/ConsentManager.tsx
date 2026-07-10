"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, ConsentGrant, ConsentRequestResult, Scan } from "@/lib/api";

/**
 * Requester surface for authorized third-party scans (T1).
 *
 * You can ask someone for permission to scan their public footprint — but YOU
 * never authorize it. We email them; they accept or decline from their own
 * inbox. Until they do, nothing about them can be scanned. This component only
 * creates asks and lists/uses/withdraws grants the subject already gave.
 */
export default function ConsentManager() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [grants, setGrants] = useState<ConsentGrant[]>([]);
  const [email, setEmail] = useState("");
  const [usernames, setUsernames] = useState("");
  const [purpose, setPurpose] = useState("");
  const [ttl, setTtl] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    api<ConsentGrant[]>("/consent/grants").then(setGrants).catch(() => {});
  }, []);

  // T1 is gated server-side; only render the surface when it's enabled.
  useEffect(() => {
    api<{ consent_t1_enabled: boolean }>("/config")
      .then((c) => {
        setEnabled(c.consent_t1_enabled);
        if (c.consent_t1_enabled) refresh();
      })
      .catch(() => setEnabled(false));
  }, [refresh]);

  if (!enabled) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const handles = usernames
        .split(/[\s,]+/)
        .map((h) => h.trim())
        .filter(Boolean);
      const res = await api<ConsentRequestResult>("/consent/requests", {
        method: "POST",
        body: { subject_email: email, usernames: handles, purpose, ttl_days: ttl },
      });
      setNotice(
        `Consent request sent to ${res.subject_email}. They'll get an email to ` +
          `authorize or decline — nothing is scanned until they accept.`
      );
      setEmail("");
      setUsernames("");
      setPurpose("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the request.");
    } finally {
      setBusy(false);
    }
  }

  async function scanNow(g: ConsentGrant) {
    setError(null);
    setNotice(null);
    try {
      await api<Scan>("/scans", {
        method: "POST",
        body: { subject_id: g.subject_id },
      });
      const subject = g.subject_email ?? g.subject_id.slice(0, 8);
      setNotice(
        `Scan started for ${subject}. Results are delivered to ${subject} — Ayin never ` +
          `shows you another person's findings. You'll only see that it ran.`
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the scan.");
    }
  }

  async function revoke(g: ConsentGrant) {
    setError(null);
    try {
      await api(`/consent/grants/${g.id}/revoke`, { method: "POST" });
      setNotice("Grant revoked — that subject can no longer be scanned by you.");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not revoke.");
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Scan someone who consents</h2>
      <p className="dim" style={{ marginTop: 0, fontSize: "0.9rem" }}>
        For security teams and protective use (e.g. an exec you safeguard). You request
        permission; <strong>they</strong> authorize it from their own inbox. Ayin never
        scans a non-consenting person — consent is verified, time-bound, and revocable by
        them at any moment.
      </p>

      {grants.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          {grants.map((g) => (
            <div
              key={g.id}
              className="status-row"
              style={{ justifyContent: "space-between", padding: "0.4rem 0" }}
            >
              <span>
                <strong>{g.subject_email ?? g.subject_id.slice(0, 8)}</strong>{" "}
                <span className="dim" style={{ fontSize: "0.85rem" }}>
                  — {g.purpose} · until {new Date(g.expires_at).toLocaleDateString()}
                </span>
              </span>
              <span style={{ display: "flex", gap: "0.5rem" }}>
                <button style={smallButton} onClick={() => scanNow(g)}>
                  Scan now
                </button>
                <button style={{ ...smallButton, color: "var(--down)" }} onClick={() => revoke(g)}>
                  Revoke
                </button>
              </span>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={submit} style={{ display: "grid", gap: "0.5rem" }}>
        <input
          style={inputStyle}
          type="email"
          required
          placeholder="Subject's email (where the consent request is sent)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          style={inputStyle}
          placeholder="Usernames to scan, space- or comma-separated (optional)"
          value={usernames}
          onChange={(e) => setUsernames(e.target.value)}
        />
        <input
          style={inputStyle}
          required
          maxLength={200}
          placeholder="Purpose (the subject sees this — e.g. 'exec protection review')"
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
        />
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <label className="dim" style={{ fontSize: "0.85rem" }}>
            Consent valid for{" "}
            <input
              style={{ ...inputStyle, width: 64 }}
              type="number"
              min={1}
              max={365}
              value={ttl}
              onChange={(e) => setTtl(Number(e.target.value))}
            />{" "}
            days
          </label>
          <button type="submit" disabled={busy} style={{ ...primaryButton, marginLeft: "auto" }}>
            {busy ? "Sending…" : "Send consent request"}
          </button>
        </div>
      </form>

      {error && <p style={{ color: "var(--down)", marginBottom: 0 }}>{error}</p>}
      {notice && <p style={{ color: "var(--ok)", marginBottom: 0 }}>{notice}</p>}
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

const smallButton: React.CSSProperties = {
  padding: "0.35rem 0.7rem",
  background: "transparent",
  color: "var(--accent)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  cursor: "pointer",
  fontSize: "0.85rem",
};

const primaryButton: React.CSSProperties = {
  padding: "0.5rem 1.1rem",
  background: "var(--accent)",
  color: "#06222e",
  border: "none",
  borderRadius: 8,
  fontWeight: 600,
  cursor: "pointer",
};
