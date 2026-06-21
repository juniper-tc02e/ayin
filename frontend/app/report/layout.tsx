import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Your exposure report",
  robots: { index: false, follow: false },
};

export default function ReportLayout({ children }: { children: React.ReactNode }) {
  return children;
}
