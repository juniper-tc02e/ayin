export const metadata = { title: "Ayin — Terms of Service & Acceptable Use" };

export default function TermsPage() {
  return (
    <main>
      <h1>Terms of Service &amp; Acceptable Use Policy</h1>
      <p className="dim">
        Version 2026-06-10 · Draft pending counsel review (PRD §19). The substance below is
        load-bearing either way: it is what the product enforces technically.
      </p>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>What Ayin is</h2>
        <p>
          Ayin shows <strong>you</strong> what publicly available sources expose about{" "}
          <strong>you</strong> — breached credentials, data-broker listings, your public
          footprint — and helps you reduce that exposure.
        </p>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Acceptable use — the short version</h2>
        <p>
          <strong>Self-scan only.</strong> You may scan only identifiers you control and have
          verified. Using Ayin to investigate, locate, monitor, or profile{" "}
          <em>anyone else</em> is prohibited and technically blocked.
        </p>
        <p>
          <strong>Prohibited uses include:</strong> scanning another person (with or without
          their knowledge); stalking, harassment, or intimidation; any hiring, tenancy,
          credit, insurance, or other eligibility decision (Ayin is not a consumer reporting
          agency and produces no information about any person&apos;s character or
          suitability); attempting to bypass verification, rate limits, or safety holds;
          scanning identifiers of anyone under 18.
        </p>
        <p>
          <strong>Enforcement:</strong> every scan is audited; abuse heuristics can refuse or
          hold scans for review; violations end in account termination and, where
          appropriate, referral to authorities.
        </p>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Your data &amp; rights</h2>
        <p>
          We keep findings and scores, not raw dossiers; sensitive data is encrypted with
          per-user keys and short retention. You can delete everything at any time
          (crypto-shred), and anyone — user or not — can exclude themselves from Ayin
          scans entirely. Every access to your data, including by our staff, is written to
          an immutable audit log.
        </p>
      </div>
    </main>
  );
}
