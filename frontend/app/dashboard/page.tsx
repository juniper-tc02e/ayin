"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, User } from "@/lib/api";
import IdentifierManager from "@/components/IdentifierManager";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.push("/login");
      })
      .finally(() => setLoading(false));
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
      <IdentifierManager />
      <div className="card">
        <p className="dim" style={{ margin: 0 }}>
          Your first scan arrives with milestone M1.
        </p>
      </div>
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
