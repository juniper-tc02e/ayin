/**
 * SEO assertion harness for SuperAyin.com.
 * Hits a running server (dev or prod) and verifies every SEO primitive the
 * redesign promises. Exits 0 if all pass, 1 otherwise.
 *
 *   BASE=http://localhost:3000 node scripts/seo-assert.mjs
 */
const BASE = process.env.BASE || "http://localhost:3000";

const results = [];
const check = (name, cond) => results.push({ name, ok: !!cond });

async function get(path) {
  const r = await fetch(BASE + path);
  const ct = r.headers.get("content-type") || "";
  const body = ct.startsWith("image/") ? "" : await r.text();
  return { status: r.status, ct, body };
}

const NOINDEX = /<meta[^>]*name="robots"[^>]*content="[^"]*noindex/i;

try {
  // ---- Landing ----
  const home = await get("/");
  check("/ → 200", home.status === 200);
  check("/ <title> contains Ayin", /<title>[^<]*Ayin[^<]*<\/title>/i.test(home.body));
  check("/ meta description", /<meta[^>]*name="description"[^>]*content="[^"]{20,}"/i.test(home.body));
  check("/ canonical → superayin.com", /rel="canonical"[^>]*superayin\.com/i.test(home.body));
  check("/ og:title", /property="og:title"/i.test(home.body));
  check("/ og:image", /property="og:image"/i.test(home.body));
  check("/ twitter:card", /name="twitter:card"/i.test(home.body));
  check("/ viewport", /name="viewport"/i.test(home.body));
  check("/ html lang=en", /<html[^>]*lang="en"/i.test(home.body));
  check("/ exactly one <h1>", (home.body.match(/<h1[\s>]/gi) || []).length === 1);
  check("/ JSON-LD Organization", home.body.includes('"@type":"Organization"'));
  check("/ JSON-LD WebSite", home.body.includes('"@type":"WebSite"'));
  check("/ JSON-LD SoftwareApplication", home.body.includes('"@type":"SoftwareApplication"'));
  check("/ JSON-LD FAQPage", home.body.includes('"@type":"FAQPage"'));
  check("/ NO SearchAction (self-scan only)", !home.body.includes('"SearchAction"'));
  check("/ NO AggregateRating", !home.body.includes("AggregateRating"));
  check("/ is indexable (no noindex)", !NOINDEX.test(home.body));

  // ---- roadmap teaser (#next) — statuses must stay honest ----
  check("/ roadmap section present", home.body.includes('id="next"'));
  check(
    "/ roadmap statuses honest (Waitlist open, no build-progress claims)",
    home.body.includes("Waitlist open") && !home.body.includes("In development")
  );

  // ---- robots.txt ----
  const robots = await get("/robots.txt");
  check("/robots.txt → 200", robots.status === 200);
  check("robots disallow /report", /Disallow:\s*\/report/i.test(robots.body));
  check("robots disallow /status", /Disallow:\s*\/status/i.test(robots.body));
  // linked private routes rely on noindex (not disallow) so crawlers can honor it
  check("robots does NOT disallow /login", !/Disallow:\s*\/login/i.test(robots.body));
  check("robots does NOT disallow /dashboard", !/Disallow:\s*\/dashboard/i.test(robots.body));
  check("robots sitemap line", /Sitemap:\s*https:\/\/superayin\.com\/sitemap\.xml/i.test(robots.body));

  // ---- sitemap.xml ----
  const sm = await get("/sitemap.xml");
  check("/sitemap.xml → 200", sm.status === 200);
  check("sitemap has /signup", sm.body.includes("https://superayin.com/signup"));
  check("sitemap has /exclude", sm.body.includes("https://superayin.com/exclude"));
  check("sitemap has /terms", sm.body.includes("https://superayin.com/terms"));
  check("sitemap EXCLUDES /dashboard", !sm.body.includes("/dashboard"));
  check("sitemap EXCLUDES /report", !sm.body.includes("/report"));

  // ---- manifest ----
  const mf = await get("/manifest.webmanifest");
  check("/manifest.webmanifest → 200", mf.status === 200);
  let manifestOk = false;
  try {
    const mj = JSON.parse(mf.body);
    manifestOk = mj.name === "Ayin" && Array.isArray(mj.icons) && mj.icons.length > 0;
  } catch {}
  check("manifest valid JSON, name=Ayin, has icons", manifestOk);

  // ---- OG image ----
  const og = await get("/opengraph-image");
  check("/opengraph-image → 200", og.status === 200);
  check("/opengraph-image is image/*", og.ct.startsWith("image/"));

  // ---- favicon ----
  const icon = await get("/icon.svg");
  check("/icon.svg → 200", icon.status === 200);

  // ---- canonical hygiene (homepage self-ref; noindex page has no homepage canonical) ----
  const HOMEPAGE_CANON = /rel="canonical"[^>]*href="https:\/\/superayin\.com\/?"/i;

  // ---- private route is noindex + must NOT canonical to the homepage ----
  const login = await get("/login");
  check("/login → 200", login.status === 200);
  check("/login is noindex", NOINDEX.test(login.body));
  check("/login has NO homepage canonical", !HOMEPAGE_CANON.test(login.body));

  // ---- public signup indexable + correct title + self-referential canonical ----
  const signup = await get("/signup");
  check("/signup → 200", signup.status === 200);
  check("/signup is indexable", !NOINDEX.test(signup.body));
  check("/signup title set", /Start your free self-scan/.test(signup.body));
  check("/signup canonical self-referential", /rel="canonical"[^>]*href="https:\/\/superayin\.com\/signup"/i.test(signup.body));
} catch (e) {
  console.error("SEO assert crashed:", e.message);
  process.exit(1);
}

const pass = results.filter((r) => r.ok).length;
const fail = results.filter((r) => !r.ok);
for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}`);
console.log(`\n${pass}/${results.length} checks passed.`);
if (fail.length) {
  console.log(`\nFAILURES:\n${fail.map((f) => "  - " + f.name).join("\n")}`);
  process.exit(1);
}
console.log("All SEO assertions passed ✓");
