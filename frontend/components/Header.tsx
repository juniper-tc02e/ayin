"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import IrisMark from "@/components/IrisMark";

/**
 * Sticky site header. Best-effort session detection swaps the marketing nav for
 * the logged-in nav; it fails soft (marketing nav) so the static landing renders
 * fine even with the API down. Marketing anchors are absolute (/#how) so they
 * resolve from any page. Mobile uses a native <details> sheet (a11y for free).
 */

type Auth = "unknown" | "in" | "out";

const MARKETING_LINKS = [
  { href: "/#how", label: "How it works" },
  { href: "/#safety", label: "Safety" },
  { href: "/#faq", label: "FAQ" },
];

export default function Header() {
  const router = useRouter();
  const [auth, setAuth] = useState<Auth>("unknown");
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    let alive = true;
    api("/auth/me")
      .then(() => alive && setAuth("in"))
      .catch(() => alive && setAuth("out"));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  async function signOut() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      /* even if the call fails, send the user home */
    }
    setAuth("out");
    router.push("/");
  }

  const loggedIn = auth === "in";

  return (
    <header className={`site-header${scrolled ? " scrolled" : ""}`}>
      <div className="container" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
        <Link href="/" className="brand iris-link" aria-label="Ayin home">
          <IrisMark size={28} decorative />
          <span>Ayin</span>
        </Link>

        {/* desktop nav */}
        <nav className="nav-links" aria-label="Primary">
          {!loggedIn &&
            MARKETING_LINKS.map((l) => (
              <Link key={l.href} href={l.href} className="nav-link">
                {l.label}
              </Link>
            ))}
          {loggedIn && (
            <Link href="/dashboard" className="nav-link">
              Dashboard
            </Link>
          )}
          <span className="nav-divider" aria-hidden />
          {loggedIn ? (
            <button onClick={signOut} className="btn btn-ghost" style={{ minHeight: 40 }}>
              Sign out
            </button>
          ) : (
            <>
              <Link href="/login" className="btn btn-ghost" style={{ minHeight: 40 }}>
                Sign in
              </Link>
              <Link href="/signup" className="btn btn-primary" style={{ minHeight: 40 }}>
                Run free scan
              </Link>
            </>
          )}
        </nav>

        {/* mobile sheet */}
        <details className="nav-mobile">
          <summary aria-label="Menu">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M3 6h18M3 12h18M3 18h18" strokeLinecap="round" />
            </svg>
          </summary>
          <div className="nav-sheet">
            {!loggedIn &&
              MARKETING_LINKS.map((l) => (
                <Link key={l.href} href={l.href}>
                  {l.label}
                </Link>
              ))}
            {loggedIn ? (
              <>
                <Link href="/dashboard">Dashboard</Link>
                <button onClick={signOut}>Sign out</button>
              </>
            ) : (
              <>
                <Link href="/login">Sign in</Link>
                <Link href="/signup" style={{ color: "var(--iris-400)", fontWeight: 600 }}>
                  Run free scan →
                </Link>
              </>
            )}
          </div>
        </details>
      </div>
    </header>
  );
}
