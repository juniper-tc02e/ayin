import Link from "next/link";
import IrisMark from "@/components/IrisMark";

const COLS: { heading: string; links: { href: string; label: string; strong?: boolean }[] }[] = [
  {
    heading: "Product",
    links: [
      { href: "/signup", label: "Run a free self-scan" },
      { href: "/#how", label: "How it works" },
      { href: "/#safety", label: "Safety & control" },
      { href: "/#faq", label: "FAQ" },
    ],
  },
  {
    heading: "Your rights",
    links: [
      { href: "/exclude", label: "Exclude me from Ayin", strong: true },
      { href: "/dashboard", label: "Delete my data", strong: true },
      { href: "/terms", label: "Terms & acceptable use" },
      { href: "/#safety", label: "Audit & retention" },
    ],
  },
  {
    heading: "Project",
    links: [
      { href: "/#agent", label: "Qwen AI Hackathon — Track 4" },
      { href: "/status", label: "System status" },
      { href: "https://github.com/juniper-tc02e/ayin", label: "GitHub" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="section--band" style={{ borderTop: "1px solid var(--line)", marginTop: "var(--sp-9)" }}>
      <div className="container" style={{ paddingBlock: "var(--sp-8)" }}>
        <div
          style={{
            display: "grid",
            gap: "var(--sp-6)",
            gridTemplateColumns: "1.3fr 1fr 1fr 1fr",
          }}
          className="footer-grid"
        >
          <div>
            <Link href="/" className="brand" aria-label="Ayin home">
              <IrisMark size={24} decorative />
              <span style={{ fontSize: "1.05rem" }}>Ayin</span>
            </Link>
            <p className="dim" style={{ fontSize: "var(--fs-sm)", maxWidth: "32ch", marginTop: "var(--sp-3)" }}>
              See what the internet knows about you — then make it forget. A free privacy
              self-scan. You only ever scan yourself.
            </p>
          </div>
          {COLS.map((col) => (
            <nav key={col.heading} aria-label={col.heading}>
              <p className="eyebrow" style={{ marginBottom: "var(--sp-3)" }}>{col.heading}</p>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--sp-2)" }}>
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link
                      href={l.href}
                      className="nav-link"
                      style={l.strong ? { color: "var(--sev-low)", fontWeight: 600 } : undefined}
                    >
                      {l.strong && <span aria-hidden>✓ </span>}
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div
          className="meta"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "var(--sp-3)",
            marginTop: "var(--sp-7)",
            paddingTop: "var(--sp-5)",
            borderTop: "1px solid var(--line)",
            color: "var(--fg-faint)",
          }}
        >
          <IrisMark size={16} />
          <span>Ayin — sight, not surveillance.</span>
          <span aria-hidden>·</span>
          <span>© 2026</span>
          <span aria-hidden>·</span>
          <span>Self-scan only. Not a consumer reporting agency.</span>
        </div>
      </div>
    </footer>
  );
}
