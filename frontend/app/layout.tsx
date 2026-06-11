import type { Metadata } from "next";
import Footer from "@/components/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ayin — see what the internet knows about you",
  description:
    "Ayin scans publicly available sources for your own exposure — breaches, data-broker listings, public footprint — scores it, and helps you shrink it. Self-scan only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Footer />
      </body>
    </html>
  );
}
