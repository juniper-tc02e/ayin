import type { Metadata } from "next";
import Link from "next/link";
import ScoreRing from "@/components/ScoreRing";
import IrisMark from "@/components/IrisMark";
import LandingEnhancements from "@/components/LandingEnhancements";

// Marketing front door: fully static, zero API dependency — it renders even if
// the backend is down (the live system-status widget lives at /status).
export const dynamic = "force-static";

// Self-referential canonical, scoped to the homepage (kept off the root layout
// so it never leaks onto noindex routes).
export const metadata: Metadata = { alternates: { canonical: "/" } };

const FAQ: { q: string; a: string }[] = [
  {
    q: "Is Ayin free?",
    a: "Yes — the self-scan is free, no card required. Ongoing monitoring and assisted removal are the paid layer, but seeing your full exposure picture once costs nothing.",
  },
  {
    q: "Can I scan someone else?",
    a: "No, and that's deliberate. Ayin only scans identifiers you've verified you control. It is not a people-search or background-check tool, and there is no way to look anyone else up — by design.",
  },
  {
    q: "Where does the data come from?",
    a: "Only publicly available sources — breach indexes, data-broker listings, and your public web footprint — reached without logging in, defeating a security control, or breaking a site's terms. We never buy breached data or touch anything about minors. Every finding carries its source and a capture date.",
  },
  {
    q: "Will you ever show my actual leaked password?",
    a: "Never. We show that a credential was exposed and in which breach — never the plaintext. The fix is the same either way: rotate it and turn on two-factor.",
  },
  {
    q: "What happens to my data after a scan?",
    a: "We store your findings and score — not a permanent dossier — encrypted and on a short retention timer. Delete everything in one click and it's crypto-shredded, unrecoverable even by us.",
  },
  {
    q: "Is my Exposure Score a judgment of me?",
    a: "No. It measures how exposed and exploitable your data is, from 0–100 — never your character, creditworthiness, or employability, and it can't be used for those decisions.",
  },
];

const FAQ_LD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQ.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
};

const HOW = [
  {
    n: "01",
    t: "Prove it's you.",
    d: "Confirm the email, phone, or username you want scanned. Ayin only ever looks at identifiers you control — nothing runs until you verify.",
  },
  {
    n: "02",
    t: "Ayin looks — across the open internet.",
    d: "Breach indexes, data-broker listings, and your public web footprint. Publicly available only: nothing behind a login, nothing bought from a leak, nothing about minors.",
  },
  {
    n: "03",
    t: "You get a plan, not a panic.",
    d: "A 0–100 Exposure Score, every finding with its source and capture date, and concrete steps to remove or lock down what's exposed.",
  },
];

const TRUST = [
  "Sources, not assertions",
  "Publicly available data only",
  "Encrypted vault + short retention",
  "Every scan audited",
];

const SAFETY = [
  {
    t: "Exclude me from Ayin",
    href: "/exclude",
    d: "Don't want to be scannable here at all? Opt out in one step — no account needed, honored permanently.",
  },
  {
    t: "Delete everything",
    href: "/dashboard",
    d: "One action crypto-shreds your data. We keep findings and your score, never a permanent dossier. Gone means gone.",
  },
  {
    t: "Sources, not assertions",
    href: null,
    d: "Every finding shows where it came from, when we captured it, and how confident we are. No mystery data.",
  },
  {
    t: "Audited from the first scan",
    href: null,
    d: "Every scan — and every access to your data, including by our own staff — writes an immutable record.",
  },
];

const WHY = [
  { t: "You hold the lens", d: "Self-scan only. We never look someone up for you." },
  {
    t: "Calm, not alarmist",
    d: "A plan, not a wall of red. Most tools profit from your fear; we profit from your control.",
  },
  {
    t: "Privacy by construction",
    d: "Short retention, crypto-shred, full audit. We never build a sellable index and never sell your data.",
  },
];

export default function LandingPage() {
  return (
    <main className="landing">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(FAQ_LD) }} />

      {/* S1 — Hero */}
      <section aria-labelledby="hero-h" className="section">
        <div
          className="container"
          style={{
            display: "grid",
            gap: "var(--sp-7)",
            gridTemplateColumns: "1.15fr 0.85fr",
            alignItems: "center",
          }}
          data-hero
        >
          <div>
            <p className="eyebrow">OSINT SELF-EXPOSURE SCANNER · QWEN AI HACKATHON · TRACK 4</p>
            <h1 id="hero-h" style={{ fontSize: "var(--fs-display)", margin: "0 0 var(--sp-4)" }}>
              See what the internet knows about you.
              <br />
              <span style={{ color: "var(--iris-400)" }}>Then make it forget.</span>
            </h1>
            <p className="lead">
              Ayin is a free self-scan that shows you your own public exposure — leaked-credential
              alerts, data-broker listings, your public footprint — scored 0 to 100, with a clear
              plan to shrink it. You scan only what you&apos;ve verified is yours.{" "}
              <strong style={{ color: "var(--fg)" }}>No one can look you up here.</strong>
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-3)", marginTop: "var(--sp-6)" }}>
              <Link href="/signup" className="btn btn-primary btn-lg">
                Run my free self-scan →
              </Link>
              <Link href="#sample" className="btn btn-ghost btn-lg">
                See a sample report
              </Link>
            </div>
            <p className="meta" style={{ marginTop: "var(--sp-4)", color: "var(--fg-faint)" }}>
              Self-scan only · no card required · exclude-me &amp; delete-everything built in
            </p>
          </div>
          <div style={{ display: "flex", justifyContent: "center" }} aria-hidden>
            <div style={{ position: "relative", filter: "drop-shadow(var(--glow-aura))" }}>
              <ScoreRing value={34} size={260} label="Sample Exposure" sublabel="lower is better" />
            </div>
          </div>
        </div>
        <span id="hero-sentinel" aria-hidden />
      </section>

      {/* S2 — Asymmetry-flip band */}
      <section aria-labelledby="flip-h" className="section section--band">
        <div className="container" style={{ textAlign: "center", maxWidth: "var(--mw-read)" }}>
          <h2 id="flip-h" style={{ fontSize: "var(--fs-h1)" }} data-reveal>
            Most tools watch people. Ayin hands you the lens.
          </h2>
          <p className="lead" style={{ margin: "var(--sp-4) auto 0" }} data-reveal>
            The person being looked at is the one doing the looking. We only ever scan you — never
            anyone else.
          </p>
        </div>
      </section>

      {/* S3 — Trust strip */}
      <section aria-label="What you can trust" className="container" style={{ paddingBlock: "var(--sp-6)" }}>
        <ul
          className="meta"
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--sp-5)",
            justifyContent: "center",
            alignItems: "center",
            color: "var(--fg-dim)",
          }}
        >
          {TRUST.map((t, i) => (
            <li key={t} style={{ display: "flex", gap: "var(--sp-3)", alignItems: "center" }}>
              <span>{t}</span>
              {i < TRUST.length - 1 && <span aria-hidden style={{ color: "var(--line-strong)" }}>·</span>}
            </li>
          ))}
        </ul>
      </section>

      {/* S4 — How it works */}
      <section id="how" aria-labelledby="how-h" className="section">
        <div className="container">
          <p className="eyebrow">HOW IT WORKS</p>
          <h2 id="how-h" style={{ fontSize: "var(--fs-h1)", maxWidth: "20ch" }} data-reveal>
            From &ldquo;what&apos;s out there?&rdquo; to &ldquo;here&apos;s the plan.&rdquo; In one scan.
          </h2>
          <div className="grid grid-3" style={{ marginTop: "var(--sp-7)" }}>
            {HOW.map((s) => (
              <div key={s.n} className="card" data-reveal>
                <span className="meta" style={{ fontSize: "1.4rem", color: "var(--iris-400)" }}>{s.n}</span>
                <h3 style={{ marginTop: "var(--sp-3)" }}>{s.t}</h3>
                <p className="dim" style={{ margin: 0, fontSize: "var(--fs-sm)" }}>{s.d}</p>
              </div>
            ))}
          </div>
          <p className="meta" style={{ marginTop: "var(--sp-5)", color: "var(--fg-faint)" }}>
            Full pipeline: INPUT → DISCOVERY → RESOLUTION → ENRICHMENT → SCORING → REPORT → REMEDIATION → MONITORING
          </p>
        </div>
      </section>

      {/* S5 — The agent / Qwen */}
      <section id="agent" aria-labelledby="agent-h" className="section section--band">
        <div
          className="container"
          style={{ display: "grid", gap: "var(--sp-7)", gridTemplateColumns: "1fr 1fr", alignItems: "center" }}
          data-cols
        >
          <div>
            <p className="eyebrow">AUTOPILOT AGENT · POWERED BY QWEN</p>
            <h2 id="agent-h" style={{ fontSize: "var(--fs-h1)" }} data-reveal>
              An agent that explains, never accuses.
            </h2>
            <p className="lead" data-reveal>
              Ayin&apos;s report is written by an autonomous agent powered by Qwen. It reads only
              your scan&apos;s real, sourced findings and explains in plain language what each one
              means and what to do first — every sentence cites the finding it rests on. It
              summarizes what&apos;s there; it never invents a finding and never decides for you.
            </p>
            <span className="pill pill-iris" style={{ marginTop: "var(--sp-4)" }}>
              Cited or silent — the agent only narrates what it actually retrieved.
            </span>
          </div>
          {/* faux NarrativePanel mirroring the real component (sample text, exposed to AT) */}
          <div className="card card--raised" data-reveal>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--sp-3)" }}>
              <h3 style={{ margin: 0 }}>What this means</h3>
              <span
                className="pill"
                style={{ color: "var(--iris-400)", borderColor: "color-mix(in srgb, var(--iris-400) 40%, transparent)" }}
              >
                ✦ written by Qwen
              </span>
            </div>
            <p style={{ margin: "var(--sp-3) 0 0" }}>
              One of your emails appears in a known breach, so the password tied to it should be
              considered public. <FauxCite n={1} />
            </p>
            <p style={{ margin: "var(--sp-2) 0 0" }}>
              Two data brokers list a home address for you — both offer a removal path. <FauxCite n={2} />
            </p>
            <p className="eyebrow" style={{ margin: "var(--sp-4) 0 var(--sp-2)" }}>Where to start</p>
            <ol style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "var(--fs-sm)" }}>
              <li>Rotate that password and turn on two-factor. <FauxCite n={1} /></li>
              <li>Submit the two broker opt-outs. <FauxCite n={2} /></li>
            </ol>
            <p className="meta" style={{ margin: "var(--sp-4) 0 0", color: "var(--fg-faint)" }}>
              Every statement cites the finding it rests on · your answer decides.
            </p>
          </div>
        </div>
      </section>

      {/* S6 — Before / After (sample) */}
      <section id="sample" aria-labelledby="sample-h" className="section">
        <div className="container">
          <h2 id="sample-h" style={{ fontSize: "var(--fs-h1)" }} data-reveal>
            This is what your report looks like.
          </h2>
          <p className="lead" data-reveal>
            Calm by design. We lead with the fix, never a wall of red — even a high score comes with
            the three things to do first.
          </p>
          <div
            className="grid"
            style={{ gridTemplateColumns: "1.2fr 0.8fr", marginTop: "var(--sp-6)", alignItems: "center" }}
            data-cols
          >
            <div className="card card--raised" data-reveal>
              <div style={{ display: "flex", gap: "var(--sp-5)", alignItems: "center", flexWrap: "wrap" }}>
                <ScoreRing value={72} size={132} label="Exposure" sublabel="before fixes" animate={false} />
                <div style={{ flex: 1, minWidth: 180 }}>
                  <SampleRow word="Sensitive" color="var(--sev-critical)" text="Email in a known breach" />
                  <SampleRow word="High" color="var(--sev-high)" text="Home address on 2 data brokers" />
                  <SampleRow word="Medium" color="var(--sev-medium)" text="Public profile links your handle" />
                  <p className="meta" style={{ margin: "var(--sp-3) 0 0", color: "var(--fg-faint)" }}>
                    source · confidence · captured — on every finding
                  </p>
                </div>
              </div>
            </div>
            <div style={{ display: "grid", gap: "var(--sp-3)" }}>
              <div className="card" data-reveal style={{ marginTop: 0 }}>
                <span className="eyebrow" style={{ margin: 0 }}>Before</span>
                <p style={{ margin: "var(--sp-1) 0 0", fontWeight: 600 }}>Exposure 72 · 9 things exposed</p>
              </div>
              <div className="card" data-reveal style={{ marginTop: 0, borderColor: "color-mix(in srgb, var(--sev-low) 45%, var(--line))" }}>
                <span className="eyebrow" style={{ margin: 0, color: "var(--sev-low)" }}>After your fixes</span>
                <p style={{ margin: "var(--sp-1) 0 0", fontWeight: 600 }}>Exposure 31 · plan in motion</p>
              </div>
              <Link href="/signup" className="btn btn-primary" style={{ marginTop: "var(--sp-1)" }}>
                Run yours →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* S7 — Safety & control */}
      <section id="safety" aria-labelledby="safety-h" className="section section--band">
        <div className="container">
          <p className="eyebrow">BUILT TO BE TRUSTED</p>
          <h2 id="safety-h" style={{ fontSize: "var(--fs-h1)", maxWidth: "22ch" }} data-reveal>
            The controls that protect you are the first thing we built.
          </h2>
          <div className="grid grid-2" style={{ marginTop: "var(--sp-7)" }}>
            {SAFETY.map((s) => (
              <div key={s.t} className="card card--glow" data-reveal>
                <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
                  <span aria-hidden style={{ color: "var(--sev-low)" }}>✓</span>
                  {s.href ? <Link href={s.href}>{s.t}</Link> : s.t}
                </h3>
                <p className="dim" style={{ margin: 0, fontSize: "var(--fs-sm)" }}>{s.d}</p>
              </div>
            ))}
          </div>
          <p className="dim" style={{ marginTop: "var(--sp-6)", maxWidth: "60ch", fontSize: "var(--fs-sm)" }}>
            We&apos;re a self-exposure scanner, not a consumer reporting agency. Ayin can&apos;t be
            used to look someone else up, or for credit, hiring, tenant, or insurance decisions.
          </p>
        </div>
      </section>

      {/* S8 — Differentiator */}
      <section aria-labelledby="why-h" className="section">
        <div className="container">
          <h2 id="why-h" style={{ fontSize: "var(--fs-h2)" }} data-reveal>Why Ayin.</h2>
          <div className="grid grid-3" style={{ marginTop: "var(--sp-6)" }}>
            {WHY.map((w) => (
              <div key={w.t} data-reveal>
                <h3 style={{ marginBottom: "var(--sp-2)" }}>{w.t}</h3>
                <p className="dim" style={{ margin: 0, fontSize: "var(--fs-sm)" }}>{w.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* S9 — FAQ */}
      <section id="faq" aria-labelledby="faq-h" className="section section--band">
        <div className="container-read">
          <p className="eyebrow">QUESTIONS</p>
          <h2 id="faq-h" style={{ fontSize: "var(--fs-h1)" }} data-reveal>Honest answers.</h2>
          <div style={{ marginTop: "var(--sp-6)" }}>
            {FAQ.map((f) => (
              <details key={f.q} className="card" style={{ marginTop: "var(--sp-3)" }}>
                <summary
                  style={{
                    cursor: "pointer",
                    fontWeight: 600,
                    fontSize: "1.05rem",
                    listStyle: "none",
                    display: "flex",
                    justifyContent: "space-between",
                    gap: "var(--sp-3)",
                  }}
                >
                  {f.q}
                  <span aria-hidden style={{ color: "var(--iris-400)" }}>+</span>
                </summary>
                <p className="dim" style={{ margin: "var(--sp-3) 0 0", fontSize: "var(--fs-sm)" }}>{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* S10 — Final CTA */}
      <section aria-labelledby="cta-h" className="section">
        <div className="container" style={{ textAlign: "center" }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--sp-4)" }} aria-hidden>
            <IrisMark size={56} animate />
          </div>
          <h2 id="cta-h" style={{ fontSize: "var(--fs-h1)" }} data-reveal>Point the lens at yourself first.</h2>
          <p className="lead" style={{ margin: "var(--sp-3) auto var(--sp-6)" }} data-reveal>
            A few minutes. One score. A plan you control.
          </p>
          <div style={{ display: "flex", gap: "var(--sp-3)", justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/signup" className="btn btn-primary btn-lg">Run my free self-scan →</Link>
            <Link href="#how" className="btn btn-ghost btn-lg">or read how it works</Link>
          </div>
        </div>
      </section>

      <span id="landing-end" aria-hidden />
      <LandingEnhancements />
    </main>
  );
}

function FauxCite({ n }: { n: number }) {
  return (
    <span
      className="meta"
      style={{
        border: "1px solid var(--line)",
        color: "var(--iris-400)",
        borderRadius: 6,
        padding: "0 0.35rem",
        marginLeft: "0.2rem",
        verticalAlign: "text-top",
      }}
    >
      {n}
    </span>
  );
}

function SampleRow({ word, color, text }: { word: string; color: string; text: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", padding: "var(--sp-1) 0" }}>
      <span className="sev-dot" style={{ background: color }} />
      <span className="meta" style={{ color, minWidth: 64 }}>{word}</span>
      <span style={{ fontSize: "var(--fs-sm)" }}>{text}</span>
    </div>
  );
}
