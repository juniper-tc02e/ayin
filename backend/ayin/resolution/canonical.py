"""Canonical exposure keys — when do two findings describe the SAME exposure?

Two findings collapse (M2-2) only when their canonical keys are equal:

- credential: breach name + the seed value it hit (two breach providers
  reporting 'ExampleBreach' for the same email = one exposure)
- social: normalized URL (scheme/case/query/fragment/trailing-slash noise
  stripped) — the same public page found via different seeds/sources
- broker: broker site + subject name value (one listing per site)
- anything else / missing key material: the finding stands alone.
"""

from urllib.parse import urlsplit, urlunsplit

from ayin.models import Finding
from ayin.models.enums import FindingCategory

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref")


def normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    # Queries are usually tracking noise for public profile/listing pages;
    # keep non-tracking params (sorted) to stay conservative.
    kept = sorted(
        p for p in parts.query.split("&")
        if p and not p.lower().startswith(_TRACKING_PREFIXES)
    )
    return urlunsplit(("https", host, path, "&".join(kept), ""))


def canonical_exposure_key(finding: Finding) -> str | None:
    """None → this finding cannot be grouped (stands alone)."""
    payload = finding.payload or {}
    if finding.category == FindingCategory.CREDENTIAL:
        breach = payload.get("breach_name")
        if breach:
            return f"credential:{str(breach).lower()}:{finding.identifier_id or ''}"
        return None
    if finding.category == FindingCategory.SOCIAL:
        if finding.source_url:
            return f"social:{normalize_url(finding.source_url)}"
        return None
    if finding.category == FindingCategory.BROKER:
        site = payload.get("broker_id") or payload.get("site")
        if site:
            return f"broker:{str(site).lower()}:{finding.identifier_id or ''}"
        return None
    return None
