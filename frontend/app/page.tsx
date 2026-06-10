import { fetchHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function LandingPage() {
  const health = await fetchHealth();

  return (
    <main>
      <h1>Ayin</h1>
      <p className="dim">
        See what the internet already knows about you — breaches, data-broker listings, your
        public footprint — scored, sourced, and fixable. <strong>Self-scan only:</strong> you can
        only scan identifiers you prove you control.
      </p>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>System status</h2>
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
              <span className={`dot ${health.redis === "ok" ? "ok" : "down"}`} /> redis:{" "}
              {health.redis}
            </div>
          </>
        ) : (
          <div className="status-row">
            <span className="dot down" /> API unreachable — is <code>docker compose up</code>{" "}
            running?
          </div>
        )}
      </div>

      <p className="dim" style={{ marginTop: "2rem", fontSize: "0.85rem" }}>
        Pre-MVP build (milestone M0). Scan onboarding, exposure report, and your data &amp; rights
        controls arrive with later milestones — see <code>docs/BUILD-PLAN.md</code>.
      </p>
    </main>
  );
}
