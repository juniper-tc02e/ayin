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
    a: "No, and that's deliberate. Ayin only scans identifiers you've verified you control. It is not a people-search or background-check tool — a request to scan anyone else is refused at the gate, and the attempt is audited.",
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
    t: "We scan public sources.",
    d: "Breach indexes, data-broker listings, and your public web footprint. Publicly available only: nothing behind a login, nothing bought from a leak, nothing about minors.",
  },
  {
    n: "03",
    t: "You get a plan.",
    d: "A 0–100 Exposure Score, every finding with its source and capture date, and concrete steps to remove or lock down what's exposed.",
  },
];

// Ordered by what's actually rare in this market: the trust architecture and
// the visible audit trail lead; the score is table stakes and goes last.
const PROOF = [
  { t: "Self-scan only, by design", d: "You verify what you own before anything runs. Scanning anyone else is refused at the gate." },
  { t: "Shows its work", d: "Every finding cites its source, and every scan records the agent's steps in an audit trail you can open." },
  { t: "0–100 scored exposure", d: "One clear number for how exploitable your data is — never a judgment of you." },
];

// The landing's sample of the real agentic audit trail (E5) — step names mirror
// the live PlannerTrail from a demo scan; no invented data, no timestamps.
const TRAIL_SAMPLE = [
  { t: "Scan requested", d: "self-scan · verified identifiers only" },
  { t: "Safety gates checked", d: "exclusions · rate limits · abuse heuristics" },
  { t: "Agent chose sources", d: "ordering decision recorded, with reasoning" },
  { t: "Sources finished", d: "findings normalized · source + capture date attached" },
  { t: "Matched & deduplicated", d: "uncertain matches held for YOUR review — never auto-merged" },
  { t: "Report written by Qwen", d: "every sentence cites a finding · citation guard enforced" },
];

const FINDINGS = [
  {
    t: "Breach exposure",
    sev: "Sensitive",
    color: "var(--sev-critical)",
    d: "Credential and account exposure in known breach indexes — status only, never plaintext.",
  },
  {
    t: "Data-broker listings",
    sev: "High",
    color: "var(--sev-high)",
    d: "Home address, phone, and relatives listed for sale — each with a removal path.",
  },
  {
    t: "Public footprint",
    sev: "Medium",
    color: "var(--sev-medium)",
    d: "Profiles and pages that surface your identifiers in open web search.",
  },
  {
    t: "Username reuse",
    sev: "Low",
    color: "var(--sev-low)",
    d: "The same handle across platforms, which can link otherwise-separate identities.",
  },
];

const SCORE_BANDS = [
  { label: "0–29", word: "Low", color: "var(--sev-low)", d: "Little exposed. Keep the habits that got you here." },
  // Boundaries mirror ScoreRing.bandColor / scoring.engine.verdict — do not drift.
  { label: "30–54", word: "Medium", color: "var(--sev-medium)", d: "Some exposure. A short list of fixes moves the needle." },
  { label: "55–79", word: "High", color: "var(--sev-high)", d: "Meaningful exposure. We lead with the three things to do first." },
  { label: "80–100", word: "Sensitive", color: "var(--sev-critical)", d: "Significant exposure — still a plan, never a wall of red." },
];

const NEVER = [
  {
    t: "Scan anyone but you",
    d: "Looking someone else up is refused at the gate and audited. Self-scan only — you verify control before anything runs.",
  },
  {
    t: "Sell your data",
    d: "We never build a sellable index and never sell subject data — not to advertisers, not to anyone.",
  },
  {
    t: "Keep a permanent dossier",
    d: "We store findings and a score, not raw records, on a short retention timer.",
  },
  {
    t: "Score you as a person",
    d: "The Exposure Score measures data exploitability, never character, credit, or employability.",
  },
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

export default function LandingPage() {
  return (
    <main className="landing">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(FAQ_LD) }} />

      {/* S1 — Hero */}
      <section aria-labelledby="hero-h" className="section section--hero">
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
            <p className="eyebrow">PRIVACY SELF-SCAN</p>
            <h1 id="hero-h" style={{ fontSize: "var(--fs-display)", margin: "0 0 var(--sp-4)" }}>
              Your exposure, measured.
            </h1>
            <p className="lead">
              See what the open internet knows about identifiers you control — breach exposure,
              data-broker listings, your public footprint — scored 0 to 100, with a clear plan to
              shrink it. <strong style={{ color: "var(--fg)" }}>Self-scan only: no one can look you up here.</strong>
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-3)", marginTop: "var(--sp-6)" }}>
              <Link href="/signup" className="btn btn-primary btn-lg">
                Run my free scan
              </Link>
              <Link href="#how" className="btn btn-ghost btn-lg">
                How it works
              </Link>
            </div>
            <ul className="trust-bar" style={{ marginTop: "var(--sp-5)" }}>
              <li>Self-scan only</li>
              <li>Sources cited</li>
              <li>Delete everything</li>
              <li>Free</li>
            </ul>
          </div>
          <div style={{ display: "flex", justifyContent: "center" }} aria-hidden>
            {/* sample readout: what a finished scan hands you — ring + category split */}
            <div className="hero-readout" style={{ filter: "drop-shadow(var(--glow-aura))" }}>
              <ScoreRing value={34} size={200} label="Sample Exposure" sublabel="lower is better" />
              <div className="readout-bars">
                {[
                  { c: "Brokers", v: 14 },
                  { c: "Credentials", v: 12 },
                  { c: "Social", v: 5 },
                  { c: "Linkage", v: 3 },
                  { c: "Records", v: 0 },
                ].map((b) => (
                  <div key={b.c} className="readout-bar">
                    <span className="meta">{b.c}</span>
                    <span className="track"><span className="fill" style={{ width: `${b.v * 2}%`, display: "block" }} /></span>
                    <span className="meta" style={{ textAlign: "right" }}>{b.v}</span>
                  </div>
                ))}
              </div>
              <p className="meta" style={{ margin: 0, color: "var(--fg-faint)" }}>sample readout · every line sourced</p>
            </div>
          </div>
        </div>
        <span id="hero-sentinel" aria-hidden />
      </section>

      {/* S2 — Proof band */}
      <section aria-labelledby="proof-h" className="section section--band">
        <div className="container">
          <h2
            id="proof-h"
            style={{
              position: "absolute",
              width: 1,
              height: 1,
              padding: 0,
              margin: -1,
              overflow: "hidden",
              clip: "rect(0,0,0,0)",
              whiteSpace: "nowrap",
              border: 0,
            }}
          >
            What Ayin guarantees
          </h2>
          <div className="proof-row">
            {PROOF.map((p) => (
              <div key={p.t} data-reveal>
                <h3 style={{ marginTop: 0 }}>{p.t}</h3>
                <p className="dim" style={{ margin: 0, fontSize: "var(--fs-sm)" }}>{p.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* S3 — How it works */}
      <section id="how" aria-labelledby="how-h" className="section">
        <div className="container">
          <p className="eyebrow">HOW IT WORKS</p>
          <h2 id="how-h" style={{ fontSize: "var(--fs-h1)", maxWidth: "20ch" }} data-reveal>
            Verify it&apos;s yours. We scan. You get a plan.
          </h2>
          <div className="trail" style={{ marginTop: "var(--sp-7)", maxWidth: "var(--mw-read)" }}>
            {HOW.map((s) => (
              <div key={s.n} className="trail-node" data-reveal>
                <span className="meta" style={{ color: "var(--iris-400)" }}>{s.n}</span>
                <h3 style={{ margin: "var(--sp-1) 0 var(--sp-1)" }}>{s.t}</h3>
                <p className="dim" style={{ margin: 0, fontSize: "var(--fs-sm)" }}>{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* S3.5 — Shows its work: the agentic audit trail, the thing nobody else has */}
      <section id="trail" aria-labelledby="trail-h" className="section">
        <div
          className="container"
          style={{ display: "grid", gap: "var(--sp-7)", gridTemplateColumns: "1fr 1.05fr", alignItems: "center" }}
          data-cols
        >
          <div>
            <p className="eyebrow">SHOWS ITS WORK</p>
            <h2 id="trail-h" style={{ fontSize: "var(--fs-h1)", maxWidth: "18ch" }} data-reveal>
              Every scan explains itself.
            </h2>
            <p className="lead" data-reveal>
              Other scanners hand you a verdict. Ayin&apos;s scan agent is accountable by
              design: which sources it chose and why, which safety gates it passed, what the
              AI wrote and what every sentence is based on — recorded step by step in an
              immutable audit log.
            </p>
            <p className="dim" style={{ fontSize: "var(--fs-sm)", maxWidth: "52ch" }} data-reveal>
              The trail beside this text mirrors a real demo scan. Yours ships with every
              report — open it any time from &ldquo;How Ayin ran this scan.&rdquo;
            </p>
          </div>
          <div className="card card--raised" data-reveal style={{ marginTop: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--sp-3)", marginBottom: "var(--sp-5)" }}>
              <span className="meta" style={{ letterSpacing: ".08em" }}>AGENT ACTIVITY</span>
              <span className="pill pill-iris">✦ audited · AI-attributed</span>
            </div>
            <div className="trail">
              {TRAIL_SAMPLE.map((s) => (
                <div key={s.t} className="trail-node">
                  <h3 style={{ margin: "0 0 2px", fontSize: "0.95rem" }}>{s.t}</h3>
                  <p className="meta" style={{ margin: 0 }}>{s.d}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* S4 — What we find */}
      <section id="findings" aria-labelledby="findings-h" className="section section--band">
        <div className="container">
          <p className="eyebrow">WHAT WE FIND</p>
          <h2 id="findings-h" style={{ fontSize: "var(--fs-h1)", maxWidth: "22ch" }} data-reveal>
            Four categories of exposure, each with a source.
          </h2>
          <div className="grid grid-2" style={{ marginTop: "var(--sp-7)" }}>
            {FINDINGS.map((f) => (
              <div key={f.t} className="card" data-reveal>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
                  <span className="sev-dot" style={{ background: f.color }} />
                  <span className="meta" style={{ color: f.color }}>{f.sev}</span>
                </div>
                <h3 style={{ margin: "var(--sp-2) 0 var(--sp-1)" }}>{f.t}</h3>
                <p className="dim" style={{ margin: 0, fontSize: "var(--fs-sm)" }}>{f.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* S5 — The score */}
      <section id="score" aria-labelledby="score-h" className="section">
        <div
          className="container"
          style={{ display: "grid", gap: "var(--sp-7)", gridTemplateColumns: "0.8fr 1.2fr", alignItems: "center" }}
          data-cols
        >
          <div style={{ display: "flex", justifyContent: "center" }} data-reveal aria-hidden>
            <ScoreRing value={52} size={200} label="Sample Exposure" sublabel="0–100" animate={false} />
          </div>
          <div>
            <p className="eyebrow">THE SCORE</p>
            <h2 id="score-h" style={{ fontSize: "var(--fs-h1)" }} data-reveal>
              One number. Never a judgment of you.
            </h2>
            <p className="lead" data-reveal>
              The Exposure Score measures how exposed and exploitable your data is — not your
              character, creditworthiness, or employability. It can&apos;t be used for hiring,
              tenant, credit, or insurance decisions.
            </p>
            <div style={{ display: "grid", gap: "var(--sp-2)", marginTop: "var(--sp-5)" }} data-reveal>
              {SCORE_BANDS.map((b) => (
                <div key={b.label} style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)" }}>
                  <span className="sev-dot" style={{ background: b.color }} />
                  <span className="meta" style={{ color: b.color, minWidth: 90 }}>{b.label} · {b.word}</span>
                  <span className="dim" style={{ fontSize: "var(--fs-sm)" }}>{b.d}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* S6 — Safety floor / what we never do */}
      <section id="safety" aria-labelledby="safety-h" className="section section--band">
        <div className="container">
          <p className="eyebrow">THE SAFETY FLOOR</p>
          <h2 id="safety-h" style={{ fontSize: "var(--fs-h1)", maxWidth: "24ch" }} data-reveal>
            What we never do — and the controls that back it up.
          </h2>
          <div className="grid grid-2" style={{ marginTop: "var(--sp-7)" }}>
            {NEVER.map((n) => (
              <div key={n.t} className="card card--never" data-reveal>
                <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
                  {/* explicit NEVER marker — these are refusals, not features */}
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style={{ flex: "none" }}>
                    <path d="M3 3l8 8M11 3l-8 8" stroke="var(--sev-critical)" strokeWidth="2" strokeLinecap="round" fill="none" />
                  </svg>
                  <span className="meta" style={{ color: "var(--sev-critical)", letterSpacing: ".08em" }}>NEVER</span>
                  {n.t}
                </h3>
                <p className="dim" style={{ margin: 0, fontSize: "var(--fs-sm)" }}>{n.d}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-2" style={{ marginTop: "var(--sp-4)" }}>
            {SAFETY.map((s) => (
              <div key={s.t} className="card card--glow" data-reveal>
                <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style={{ flex: "none" }}>
                    <path d="M2.5 7.5l3 3 6-7" stroke="var(--sev-low)" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
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

      {/* S7 — FAQ */}
      <section id="faq" aria-labelledby="faq-h" className="section">
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
                  <span aria-hidden className="faq-marker" style={{ color: "var(--iris-400)" }}>+</span>
                </summary>
                <p className="dim" style={{ margin: "var(--sp-3) 0 0", fontSize: "var(--fs-sm)" }}>{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* S8 — Final CTA */}
      <section aria-labelledby="cta-h" className="section section--band">
        <div className="container" style={{ textAlign: "center" }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--sp-4)" }} aria-hidden>
            <IrisMark size={56} animate />
          </div>
          <h2 id="cta-h" style={{ fontSize: "var(--fs-h1)" }} data-reveal>
            See what the internet knows about you — then make it forget.
          </h2>
          <p className="lead" style={{ margin: "var(--sp-3) auto var(--sp-6)" }} data-reveal>
            A few minutes. One score. A plan you control.
          </p>
          <div style={{ display: "flex", gap: "var(--sp-3)", justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/signup" className="btn btn-primary btn-lg">Run my free scan</Link>
            <Link href="#how" className="btn btn-ghost btn-lg">or read how it works</Link>
          </div>
          <p className="meta" style={{ marginTop: "var(--sp-4)", color: "var(--fg-faint)" }}>
            Self-scan only · no card required · exclude-me &amp; delete-everything built in
          </p>
        </div>
      </section>

      <span id="landing-end" aria-hidden />
      <LandingEnhancements />
    </main>
  );
}
