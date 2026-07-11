import Link from "next/link";
import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";
import IrisMark from "@/components/IrisMark";

export const metadata: Metadata = {
  title: "Start your free self-scan",
  description:
    "Create your Ayin account and run a free self-scan. You only ever scan identifiers you verify you control — self-scan only.",
  alternates: { canonical: "/signup" },
};

export default function SignupPage() {
  return (
    <main
      style={{
        maxWidth: 440,
        background: "var(--ink-800)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-lg, 16px)",
        padding: "var(--sp-6, 2.5rem) var(--sp-5)",
      }}
    >
      <div style={{ textAlign: "center", marginBottom: "var(--sp-5)" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--sp-3)" }}>
          <IrisMark size={44} />
        </div>
        <h1 style={{ fontSize: "var(--fs-h1)", margin: 0 }}>Start your free self-scan</h1>
        <p className="dim" style={{ marginTop: "var(--sp-2)" }}>
          We verify each identifier before anything scans — starting with this email.
        </p>
      </div>
      <AuthForm mode="signup" />
      <p className="dim" style={{ marginTop: "var(--sp-4)", textAlign: "center" }}>
        Already have an account? <Link href="/login">Sign in</Link>
      </p>
    </main>
  );
}
