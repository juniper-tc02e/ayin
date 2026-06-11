"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

type Identifier = {
  id: string;
  kind: string;
  value: string;
  verification_state: "unverified" | "pending" | "verified";
  challengeable: boolean;
  verified_at: string | null;
  created_at: string;
};

const KINDS = [
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "username", label: "Username" },
  { value: "full_name", label: "Full name" },
  { value: "city", label: "City" },
];

const stateColor: Record<Identifier["verification_state"], string> = {
  verified: "var(--ok)",
  pending: "var(--warn)",
  unverified: "var(--text-dim)",
};

export default function IdentifierManager({
  onChange,
}: {
  onChange?: (count: number) => void;
}) {
  const [rows, setRows] = useState<Identifier[]>([]);
  const [kind, setKind] = useState("email");
  const [value, setValue] = useState("");
  const [otpFor, setOtpFor] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<Identifier[]>("/identifiers")
      .then((r) => {
        setRows(r);
        onChange?.(r.length);
      })
      .catch(() => {});
  }, [onChange]);

  useEffect(refresh, [refresh]);

  async function run(fn: () => Promise<unknown>, okMessage?: string) {
    setError(null);
    setNotice(null);
    try {
      await fn();
      if (okMessage) setNotice(okMessage);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Your identifiers</h2>
      <p className="dim" style={{ marginTop: 0, fontSize: "0.9rem" }}>
        Ayin scans only what you add here — and sensitive results stay hidden until you
        verify control. Usernames, names, and cities are auxiliary seeds refining your scan.
      </p>

      {rows.map((r) => (
        <div
          key={r.id}
          className="status-row"
          style={{ justifyContent: "space-between", padding: "0.4rem 0" }}
        >
          <span>
            <code>{r.kind}</code> {r.value}{" "}
            <span style={{ color: stateColor[r.verification_state], fontSize: "0.85rem" }}>
              {r.verification_state}
            </span>
          </span>
          <span style={{ display: "flex", gap: "0.5rem" }}>
            {r.challengeable && r.verification_state !== "verified" && (
              <button
                style={smallButton}
                onClick={() =>
                  run(async () => {
                    await api(`/identifiers/${r.id}/send-challenge`, { method: "POST" });
                    if (r.kind === "phone") setOtpFor(r.id);
                  }, r.kind === "phone" ? "Code sent." : "Verification email sent.")
                }
              >
                {r.kind === "phone" ? "Send code" : "Send link"}
              </button>
            )}
            {r.kind === "phone" && r.verification_state === "pending" && otpFor !== r.id && (
              <button style={smallButton} onClick={() => setOtpFor(r.id)}>
                Enter code
              </button>
            )}
            <button
              style={{ ...smallButton, color: "var(--down)" }}
              onClick={() =>
                run(
                  () => api(`/identifiers/${r.id}`, { method: "DELETE" }),
                  "Identifier and its findings removed."
                )
              }
            >
              Remove
            </button>
          </span>
        </div>
      ))}

      {otpFor && (
        <form
          style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await api(`/identifiers/${otpFor}/verify-otp`, {
                method: "POST",
                body: { code: otp },
              });
              setOtpFor(null);
              setOtp("");
            }, "Phone verified.");
          }}
        >
          <input
            style={{ ...inputStyle, maxWidth: 140 }}
            placeholder="6-digit code"
            value={otp}
            inputMode="numeric"
            pattern="\d{6}"
            onChange={(e) => setOtp(e.target.value)}
          />
          <button type="submit" style={smallButton}>
            Verify
          </button>
        </form>
      )}

      <form
        style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", flexWrap: "wrap" }}
        onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            const created = await api<Identifier>("/identifiers", {
              method: "POST",
              body: { kind, value },
            });
            setValue("");
            if (created.kind === "phone") setOtpFor(created.id);
          }, kind === "email" ? "Added — verification email sent." : kind === "phone" ? "Added — code sent." : "Added.");
        }}
      >
        <select value={kind} onChange={(e) => setKind(e.target.value)} style={inputStyle}>
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        <input
          style={{ ...inputStyle, flex: 1, minWidth: 220 }}
          placeholder={kind === "phone" ? "+15551234567" : "value"}
          value={value}
          required
          onChange={(e) => setValue(e.target.value)}
        />
        <button type="submit" style={smallButton}>
          Add
        </button>
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
