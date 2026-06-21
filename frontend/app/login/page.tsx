import Link from "next/link";
import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";
import IrisMark from "@/components/IrisMark";

export const metadata: Metadata = {
  title: "Sign in",
  robots: { index: false, follow: false },
};

export default function LoginPage() {
  return (
    <main style={{ maxWidth: 440 }}>
      <div style={{ textAlign: "center", marginBottom: "var(--sp-5)" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--sp-3)" }}>
          <IrisMark size={44} />
        </div>
        <h1 style={{ fontSize: "var(--fs-h1)", margin: 0 }}>Welcome back</h1>
        <p className="dim" style={{ marginTop: "var(--sp-2)" }}>
          See what the internet knows about you.
        </p>
      </div>
      <AuthForm mode="login" />
      <p className="dim" style={{ marginTop: "var(--sp-4)", textAlign: "center" }}>
        New here? <Link href="/signup">Start your free self-scan</Link>
      </p>
    </main>
  );
}
