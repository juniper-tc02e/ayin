import Link from "next/link";
import type { Metadata } from "next";
import { apiBase, type Health } from "@/lib/api";

export const metadata: Metadata = {
  title: "System status",
  robots: { index: false, follow: false },
};

// Inlined instead of lib/api's fetchHealth() — that helper forces
// cache: "no-store" on every call, which meant any transient DB/Redis
// hiccup was instantly visible to anyone (this page is linked from every
// footer). Fetching with next.revalidate lets this page ride Next's ISR
// cache: at most 30s stale, without touching lib/api.ts's contract for
// callers that need the always-fresh version.
async function getHealth(): Promise<{ health: Health | null; checkedAt: string }> {
  const checkedAt = new Date().toISOString();
  try {
    const res = await fetch(`${apiBase()}/health`, { next: { revalidate: 30 } });
    if (!res.ok) return { health: null, checkedAt };
    return { health: (await res.json()) as Health, checkedAt };
  } catch {
    return { health: null, checkedAt };
  }
}

function statusLabel(ok: boolean): string {
  return ok ? "Operational" : "Needs attention";
}

function formatCheckedAt(iso: string): string {
  return `${iso.replace("T", " ").slice(0, 19)} UTC`;
}

export default async function StatusPage() {
  const { health, checkedAt } = await getHealth();

  return (
    <main>
      <p style={{ margin: "0 0 var(--sp-2)" }}>
        <Link href="/" className="dim">← Home</Link>
      </p>
      <h1>System status</h1>
      <p className="lead">
        Health of the Ayin API and its datastores, checked at most every 30 seconds.
      </p>

      <div className="card">
        {health ? (
          <>
            <div className="status-row">
              <span className={`dot ${health.status === "ok" ? "ok" : "degraded"}`} />
              API <code>v{health.version}</code> — {statusLabel(health.status === "ok")}
            </div>
            <div className="status-row">
              <span className={`dot ${health.db === "ok" ? "ok" : "down"}`} /> database:{" "}
              {statusLabel(health.db === "ok")}
            </div>
            <div className="status-row">
              <span className={`dot ${health.redis === "ok" ? "ok" : "down"}`} /> redis:{" "}
              {statusLabel(health.redis === "ok")}
            </div>
          </>
        ) : (
          <div className="status-row">
            <span className="dot down" /> API unreachable.
          </div>
        )}
      </div>

      <p className="dim" style={{ marginTop: "var(--sp-3)", fontSize: "var(--fs-sm)" }}>
        Last checked {formatCheckedAt(checkedAt)}.
      </p>

      <p className="dim" style={{ marginTop: "var(--sp-5)", fontSize: "var(--fs-sm)" }}>
        This page is for operators and is excluded from search. Looking for the product?{" "}
        <Link href="/">See what the internet knows about you →</Link>
      </p>
    </main>
  );
}
