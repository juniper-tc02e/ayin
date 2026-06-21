import type { Metadata, Viewport } from "next";
import { Fraunces, Inter, IBM_Plex_Mono } from "next/font/google";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  axes: ["opsz"],
  variable: "--font-fraunces",
});
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "800"],
  variable: "--font-inter",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://superayin.com"),
  title: {
    default: "Ayin — See what the internet knows about you",
    template: "%s · Ayin",
  },
  description:
    "Run a free self-scan to see your public exposure — leaked-credential alerts, data-broker listings, your public footprint — scored 0–100, with a plan to shrink it. Self-scan only.",
  keywords: [
    "self-exposure scan",
    "what does the internet know about me",
    "check my data breaches free",
    "data broker opt out",
    "personal OSINT scan",
    "exposure score",
    "privacy footprint check",
  ],
  applicationName: "Ayin",
  authors: [{ name: "Ayin" }],
  // Canonical is declared per-page (homepage in app/page.tsx; public child
  // routes in their own metadata) so it never leaks onto noindex routes.
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    siteName: "Ayin",
    url: "https://superayin.com",
    locale: "en_US",
    title: "Ayin — See what the internet knows about you, then make it forget",
    description:
      "Free privacy self-scan · Self-scan only · Exposure Score 0–100 · a calm plan to shrink it.",
    // og:image + twitter:image come from the app/opengraph-image.tsx file
    // convention (single source, content-hashed URL).
  },
  twitter: {
    card: "summary_large_image",
    title: "Ayin — See what the internet knows about you",
    description:
      "Free privacy self-scan. Self-scan only. Exposure Score + a plan to shrink it.",
  },
};

export const viewport: Viewport = { themeColor: "#0b0e14" };

// Site-wide structured data. No PII, no AggregateRating, and no SearchAction —
// there is no people-search here, and faking one would contradict self-scan-only.
const ORG_LD = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Ayin",
  url: "https://superayin.com",
  logo: "https://superayin.com/icon.svg",
  description:
    "A privacy self-exposure scanner. See what the open internet exposes about identifiers you control, get an Exposure Score, and a plan to shrink it. Self-scan only.",
  slogan: "See what the internet knows about you — then make it forget.",
  sameAs: ["https://devpost.com/software/ayin"],
};
const SITE_LD = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Ayin",
  url: "https://superayin.com",
};
const APP_LD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Ayin",
  applicationCategory: "SecurityApplication",
  operatingSystem: "Web",
  url: "https://superayin.com",
  description:
    "Free OSINT self-exposure scan. See breaches, data-broker listings, and your public footprint for identifiers you control; get a 0–100 Exposure Score and a plan to shrink it. Self-scan only.",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  featureList: [
    "Self-scan only",
    "Exposure Score 0–100",
    "Sourced findings",
    "Data-broker opt-out guidance",
    "Qwen-written report",
    "Exclude-me and delete-everything controls",
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${inter.variable} ${plexMono.variable}`}>
      <body>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_LD) }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(SITE_LD) }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(APP_LD) }} />

        <a href="#main-content" className="skip-link">Skip to content</a>
        <Header />
        <div id="main-content" tabIndex={-1}>{children}</div>
        <Footer />
      </body>
    </html>
  );
}
