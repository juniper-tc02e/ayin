import Link from "next/link";
import type { Metadata } from "next";
import { fetchHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "System status",
  robots: { index: false, follow: false },
};

export default async function StatusPage() {
  const health = await fetchHealth();

  return (
    <main>
      <p style={{ margin: "0 0 var(--sp-2)" }}>
        <Link href="/" className="dim">← Home</Link>
      </p>
      <h1>System status</h1>
      <p className="lead">Live health of the Ayin API and its datastores.</p>

      <div className="card">
        {health ? (
          <>
            <div className="status-row">
              <span className={`dot ${health.status === "ok" ? "ok" : "degraded"}`} />
              API <code>v{health.version}</code> — {health.status}
            </div>
            <div className="status-row">
              <span className={`dot ${health.db === "ok" ? "ok" : "down"}`} /> database: {health.db}
            </div>
            <div className="status-row">
              <span className={`dot ${health.redis === "ok" ? "ok" : "down"}`} /> redis: {health.redis}
            </div>
          </>
        ) : (
          <div className="status-row">
            <span className="dot down" /> API unreachable.
          </div>
        )}
      </div>

      <p className="dim" style={{ marginTop: "var(--sp-5)", fontSize: "var(--fs-sm)" }}>
        This page is for operators and is excluded from search. Looking for the product?{" "}
        <Link href="/">See what the internet knows about you →</Link>
      </p>
    </main>
  );
}
