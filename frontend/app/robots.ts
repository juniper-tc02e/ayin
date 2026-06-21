import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  // /login and /dashboard are linked from the chrome and carry meta noindex —
  // we DON'T disallow them, so crawlers can fetch the page and honor noindex
  // (a disallowed URL can still get indexed as a bare listing). We only block
  // token/data routes that should never be crawled at all.
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/report",
        "/verify-email",
        "/verify-identifier",
        "/exclude/confirm",
        "/status",
      ],
    },
    sitemap: "https://superayin.com/sitemap.xml",
  };
}
