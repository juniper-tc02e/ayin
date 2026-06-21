import type { MetadataRoute } from "next";

// Only public, indexable marketing routes. App + verification routes are
// noindex (see app/robots.ts and per-route metadata).
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://superayin.com";
  const now = new Date();
  return ["/", "/signup", "/exclude", "/terms"].map((p) => ({
    url: `${base}${p}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: p === "/" ? 1 : 0.7,
  }));
}
