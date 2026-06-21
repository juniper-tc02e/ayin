"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

/**
 * Progressive enhancement for the static landing page: reveals [data-reveal]
 * elements as they scroll in, and shows a sticky mobile CTA once the hero
 * leaves the viewport. Pure client effects — the server-rendered page is fully
 * usable (and fully visible) without any of this.
 */
export default function LandingEnhancements() {
  const [showCta, setShowCta] = useState(false);

  useEffect(() => {
    // Scroll reveals: hide only below-fold elements (add .pre), reveal on
    // scroll-in (remove .pre). Above-fold stays visible → no flash; nothing
    // mutates <html> → no hydration mismatch; reduced-motion forces all visible.
    const reveals = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    const revObs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.remove("pre");
            revObs.unobserve(e.target);
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.05 }
    );
    const fold = window.innerHeight * 0.9;
    reveals.forEach((el) => {
      if (el.getBoundingClientRect().top > fold) {
        el.classList.add("pre");
        revObs.observe(el);
      }
    });

    // Sticky CTA: show once the hero scrolls out, hide again as the page end
    // nears so it never overlaps the final CTA + footer legal line on mobile.
    let heroPassed = false;
    let atEnd = false;
    const update = () => setShowCta(heroPassed && !atEnd);
    const hero = document.getElementById("hero-sentinel");
    const end = document.getElementById("landing-end");
    const heroObs = hero
      ? new IntersectionObserver(([e]) => { heroPassed = !e.isIntersecting; update(); }, { threshold: 0 })
      : null;
    const endObs = end
      ? new IntersectionObserver(([e]) => { atEnd = e.isIntersecting; update(); }, {
          rootMargin: "0px 0px 140px 0px",
          threshold: 0,
        })
      : null;
    if (hero && heroObs) heroObs.observe(hero);
    if (end && endObs) endObs.observe(end);

    return () => {
      revObs.disconnect();
      heroObs?.disconnect();
      endObs?.disconnect();
    };
  }, []);

  return (
    <div className={`sticky-cta${showCta ? " show" : ""}`}>
      <Link
        href="/signup"
        className="btn btn-primary"
        style={{ width: "100%" }}
      >
        Run your free self-scan →
      </Link>
    </div>
  );
}
