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
      { href: "https://devpost.com/software/ayin", label: "Built for the Qwen AI Hackathon" },
      { href: "/status", label: "System status" },
      { href: "https://github.com/juniper-tc02e/ayin", label: "GitHub" },
      { href: "mailto:abuse@superayin.com?subject=Consent%20request%20abuse%20report", label: "Report abuse" },
    ],
  },
];

const SAFETY_FLOOR = [
  "Self-scan only",
  "Sourced findings",
  "Delete everything",
  "Audit log",
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
            <p className="lead" style={{ fontSize: "var(--fs-sm)", maxWidth: "32ch", marginTop: "var(--sp-3)" }}>
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
                      {l.strong && (
                        <svg
                          width="13"
                          height="13"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden
                          style={{ marginRight: "6px", verticalAlign: "-1px" }}
                        >
                          <path d="M20 6 9 17l-5-5" />
                        </svg>
                      )}
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        {/* safety-floor strip — the real, non-negotiable guarantees, mono/provenance styling */}
        <ul
          className="meta trust-bar"
          style={{
            listStyle: "none",
            margin: "var(--sp-7) 0 0",
            padding: "var(--sp-4) 0",
            borderTop: "1px solid var(--line)",
            borderBottom: "1px solid var(--line)",
          }}
        >
          {SAFETY_FLOOR.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>

        <div
          className="meta"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "var(--sp-3)",
            marginTop: "var(--sp-5)",
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
