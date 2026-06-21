import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Exclusion confirmed",
  robots: { index: false, follow: false },
};

export default function ExcludeConfirmLayout({ children }: { children: React.ReactNode }) {
  return children;
}
