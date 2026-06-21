import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verify identifier",
  robots: { index: false, follow: false },
};

export default function VerifyIdentifierLayout({ children }: { children: React.ReactNode }) {
  return children;
}
