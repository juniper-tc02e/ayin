import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Exclude yourself from Ayin",
  description:
    "Don't want to be scannable on Ayin at all? Opt out in one step — no account needed, honored permanently.",
  alternates: { canonical: "/exclude" },
};

export default function ExcludeLayout({ children }: { children: React.ReactNode }) {
  return children;
}
