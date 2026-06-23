"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, User } from "@/lib/api";
import IdentifierManager from "@/components/IdentifierManager";
import TosGate from "@/components/TosGate";
import ScanPanel from "@/components/ScanPanel";
import ConsentManager from "@/components/ConsentManager";
import DataRights from "@/components/DataRights";
import GettingStarted from "@/components/GettingStarted";
import ScanPreview from "@/components/ScanPreview";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [identifierCount, setIdentifierCount] = useState(0);
  const [tosAccepted, setTosAccepted] = useState(false);
  const [hasScanned, setHasScanned] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);

  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.push("/login");
      })
      .finally(() => setLoading(false));
    api<{ accepted_current: boolean }>("/tos")
      .then((t) => setTosAccepted(t.accepted_current))
      .catch(() => {});
    api<{ id: string }[]>("/scans")
      .then((s) => setHasScanned(s.length > 0))
      .catch(() => {});
  }, [router]);

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.push("/");
  }

  if (loading) return <main><p className="dim">Loading…</p></main>;
  if (!user) return null;

  return (
    <main>
      <h1>Your exposure</h1>
      <div className="card">
        <p style={{ marginTop: 0 }}>
          Signed in as <strong>{user.email}</strong>{" "}
          {user.email_verified ? (
            <span style={{ color: "var(--ok)" }}>✓ verified</span>
          ) : (
            <span style={{ color: "var(--warn)" }}>— verification pending</span>
          )}
        </p>
        {!user.email_verified && (
          <p className="dim" style={{ margin: 0 }}>
            Check your inbox for the verification link. Results stay hidden until you
            verify control of your identifiers. (Local dev: emails land in MailDev at{" "}
            <code>http://localhost:1080</code>.)
          </p>
        )}
      </div>
      {user && (
        <GettingStarted
          user={user}
          identifierCount={identifierCount}
          tosAccepted={tosAccepted}
          hasScanned={hasScanned}
        />
      )}
      <TosGate />
      <IdentifierManager
        onChange={(n) => {
          setIdentifierCount(n);
          setPreviewKey((v) => v + 1);
        }}
      />
      <ScanPreview refreshKey={previewKey} />
      <ScanPanel />
      <ConsentManager />
      <DataRights />
      <p style={{ marginTop: "1.5rem" }}>
        <button
          onClick={logout}
          style={{
            padding: "0.5rem 1rem",
            background: "transparent",
            color: "var(--text-dim)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          Log out
        </button>
      </p>
    </main>
  );
}
