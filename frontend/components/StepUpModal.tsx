"use client";

import { useEffect, useRef, useState } from "react";
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
  const passwordRef = useRef<HTMLInputElement>(null);
  const submitRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Minimal manual focus trap (no new dependency): remember what had focus
  // before the dialog opened, move focus into the dialog, cycle Tab/Shift+Tab
  // across the dialog's three focusable elements, restore focus on close.
  // Escape closes the dialog (keyboard parity with the scrim click).
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    passwordRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const focusable = ([passwordRef.current, submitRef.current, cancelRef.current] as (HTMLElement | null)[]).filter(
        (el): el is HTMLElement => el !== null
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement as HTMLElement | null;
      const currentIndex = current ? focusable.indexOf(current) : -1;
      if (e.shiftKey) {
        if (currentIndex <= 0) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (currentIndex === -1 || currentIndex === focusable.length - 1) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previouslyFocused?.focus();
    };
  }, [onClose]);

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
        role="dialog"
        aria-modal="true"
        aria-labelledby="stepup-title"
      >
        <h2 id="stepup-title" style={{ marginTop: 0, fontSize: "1rem" }}>Confirm it&apos;s you</h2>
        <p className="dim" style={{ fontSize: "0.9rem" }}>
          Credential-exposure details are extra sensitive, so we ask for your password
          again before showing them. The unlock lasts a few minutes and is logged to
          your audit trail.
        </p>
        <input
          ref={passwordRef}
          type="password"
          required
          autoComplete="current-password"
          aria-label="Your password"
          placeholder="Your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{
            display: "block", width: "100%", padding: "0.5rem 0.75rem",
            background: "var(--bg)", color: "var(--text)",
            border: "1px solid var(--border)", borderRadius: 8, marginBottom: "0.75rem",
          }}
        />
        {error && (
          <p role="alert" style={{ color: "var(--down)", marginTop: 0 }}>
            {error}
          </p>
        )}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            ref={submitRef}
            type="submit"
            disabled={busy}
            style={{
              padding: "0.5rem 1rem", background: "var(--accent)", color: "var(--on-iris)",
              border: "none", borderRadius: 8, fontWeight: 600, cursor: "pointer",
            }}
          >
            {busy ? "…" : "Unlock details"}
          </button>
          <button
            ref={cancelRef}
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
