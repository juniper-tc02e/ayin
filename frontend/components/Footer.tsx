import Link from "next/link";

export default function Footer() {
  return (
    <footer
      style={{
        maxWidth: 720, margin: "3rem auto 2rem", padding: "1rem 1.5rem 0",
        borderTop: "1px solid var(--border)", fontSize: "0.8rem",
      }}
      className="dim"
    >
      <p style={{ margin: 0 }}>
        Ayin scans only people who prove it&apos;s them. Don&apos;t want to be scannable at
        all? <Link href="/exclude">Exclude yourself from Ayin</Link> — no account needed.
      </p>
      <p style={{ margin: "0.4rem 0 0" }}>
        <Link href="/terms">Terms &amp; acceptable use</Link> · We keep findings and scores,
        never raw dossiers; every access is audited.
      </p>
    </footer>
  );
}
