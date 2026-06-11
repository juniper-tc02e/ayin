"use client";

import { User } from "@/lib/api";

export default function GettingStarted({
  user,
  identifierCount,
  tosAccepted,
  hasScanned,
}: {
  user: User;
  identifierCount: number;
  tosAccepted: boolean;
  hasScanned: boolean;
}) {
  if (hasScanned) return null;
  const steps: { label: string; done: boolean }[] = [
    { label: "Verify your email — proves the scan is about you", done: user.email_verified },
    {
      label: `Add what you know about yourself (${identifierCount} added) — usernames, a second email, your name & city`,
      done: identifierCount > 1,
    },
    { label: "Accept the terms — self-scan only, in plain words", done: tosAccepted },
    { label: "Run your first scan and get your Exposure Score", done: false },
  ];
  return (
    <div className="card" style={{ borderColor: "var(--accent)" }}>
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Getting started</h2>
      {steps.map((s, i) => (
        <p key={i} style={{ margin: "0.3rem 0", fontSize: "0.9rem" }}>
          <span style={{ color: s.done ? "var(--ok)" : "var(--text-dim)" }}>
            {s.done ? "✓" : `${i + 1}.`}
          </span>{" "}
          <span className={s.done ? "dim" : undefined}>{s.label}</span>
        </p>
      ))}
    </div>
  );
}
