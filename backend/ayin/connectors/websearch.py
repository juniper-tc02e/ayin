"""Public-web/social discovery connector — compliant search API (FR-DISC-2, M1-3).

Uses a licensed search API (Brave-Search-shaped). The connector consumes only
what the API returns — URL, title, snippet — and never fetches result pages
itself in the MVP, so the "publicly available" line (PRD §11.1) is enforced
by construction: nothing behind a login, no robots/ToS exposure.

Namesake honesty: confidence is keyed to the seed kind. An exact email match
is strong; a bare name match is weak and stays clearly marked until entity
resolution (M2-1) lets the user confirm/reject.
"""

import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from ayin.config import get_settings
from ayin.connectors.base import (
    AccessMethod,
    Connector,
    ConnectorAuthError,
    ConnectorPermanentError,
    ConnectorTransientError,
    NormalizedFinding,
    RawResult,
    SeedQuery,
    SourceGovernance,
)
from ayin.connectors.registry import registry
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

log = logging.getLogger("ayin.connectors.websearch")

MAX_RESULTS_PER_SEED = 20

_PLATFORMS = {
    "twitter.com": "X (Twitter)", "x.com": "X (Twitter)",
    "linkedin.com": "LinkedIn", "facebook.com": "Facebook",
    "instagram.com": "Instagram", "github.com": "GitHub",
    "reddit.com": "Reddit", "tiktok.com": "TikTok",
    "youtube.com": "YouTube", "medium.com": "Medium",
    "pinterest.com": "Pinterest", "threads.net": "Threads",
}

_BASE_CONFIDENCE = {
    IdentifierKind.EMAIL: 0.7,
    IdentifierKind.USERNAME: 0.5,
    IdentifierKind.FULL_NAME: 0.4,
}


def _platform(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain, label in _PLATFORMS.items():
        if host == domain or host.endswith("." + domain):
            return label
    return host or "web"


def _dedupe_url(url: str) -> str:
    return url if len(url) <= 180 else hashlib.sha256(url.encode()).hexdigest()


@registry.register
class WebSearchConnector(Connector):
    id = "websearch"
    name = "Public Web Search"
    version = "0.1.0"
    governance = SourceGovernance(
        legal_basis=(
            "Licensed web-search API (Brave-Search-class): returns titles, URLs and "
            "snippets of publicly indexed pages. The connector never fetches result "
            "pages or anything behind authentication (PRD §11.1)."
        ),
        access_method=AccessMethod.LICENSED_API,
        tos_ref="https://brave.com/search/api/ (API terms)",
        data_classes=["result-url", "page-title", "snippet", "page-age"],
        cost_per_call_usd=0.005,
        rate_limit_per_minute=60,
        counsel_signoff=False,  # flip with the API agreement on file (PRD §11.4)
    )
    supported_kinds = frozenset(
        {IdentifierKind.EMAIL, IdentifierKind.USERNAME, IdentifierKind.FULL_NAME}
    )

    def __init__(self, *, transport: httpx.BaseTransport | None = None, **kw):
        super().__init__(**kw)
        settings = get_settings()
        self._api_key = settings.search_api_key
        self._base = settings.search_api_base_url.rstrip("/")
        self._transport = transport

    def authenticate(self) -> None:
        if not self._api_key:
            raise ConnectorAuthError(
                "search connector: SEARCH_API_KEY not configured — refusing to run"
            )

    def _query(self, seed: SeedQuery) -> str:
        q = f'"{seed.value}"'
        if seed.kind == IdentifierKind.FULL_NAME and seed.context.get("city"):
            q += f' "{seed.context["city"]}"'
        return q

    def fetch(self, seed: SeedQuery) -> list[RawResult]:
        with httpx.Client(transport=self._transport, timeout=15) as client:
            try:
                res = client.get(
                    f"{self._base}/web/search",
                    params={"q": self._query(seed), "count": MAX_RESULTS_PER_SEED},
                    headers={
                        "X-Subscription-Token": self._api_key,
                        "user-agent": "Ayin-SelfScan/0.1 (defensive self-exposure scan)",
                    },
                )
            except httpx.TransportError as exc:
                raise ConnectorTransientError(f"search API unreachable: {exc}") from exc
        if res.status_code in (401, 403):
            raise ConnectorAuthError(f"search API rejected credentials ({res.status_code})")
        if res.status_code == 429 or res.status_code >= 500:
            raise ConnectorTransientError(f"search API throttled/unavailable ({res.status_code})")
        if res.status_code != 200:
            raise ConnectorPermanentError(f"search API unexpected status {res.status_code}")
        now = datetime.now(timezone.utc)
        results = (res.json().get("web") or {}).get("results") or []
        return [RawResult(payload=r, fetched_at=now) for r in results[:MAX_RESULTS_PER_SEED]]

    def normalize(self, seed: SeedQuery, raw: list[RawResult]) -> list[NormalizedFinding]:
        out = []
        base_confidence = _BASE_CONFIDENCE.get(seed.kind, 0.4)
        for r in raw:
            url = str(r.payload.get("url", "")).strip()
            if not url.startswith(("http://", "https://")):
                continue  # untrusted input — drop junk rows
            title = str(r.payload.get("title", "")).strip() or url
            snippet = str(r.payload.get("description", "")).strip()
            platform = _platform(url)
            # A page that displays the seed verbatim in its snippet is showing
            # the data publicly right now → slightly more sensitive/confident.
            verbatim = seed.value.lower() in (title + " " + snippet).lower()
            confidence = min(0.9, base_confidence + (0.15 if verbatim else 0.0))
            if seed.kind == IdentifierKind.FULL_NAME and seed.context.get("city"):
                confidence = min(0.9, confidence + 0.05)
            out.append(
                NormalizedFinding(
                    category=FindingCategory.SOCIAL,
                    sensitivity=Sensitivity.MEDIUM if verbatim else Sensitivity.LOW,
                    source=self.id,
                    source_name=self.name,
                    source_url=url,
                    captured_at=r.fetched_at,
                    confidence=round(confidence, 2),
                    summary=(
                        f"Public {platform} result mentioning this "
                        f"{seed.kind.value.replace('_', ' ')}: “{title[:120]}”"
                        + (" — the value itself is visible on the page." if verbatim else "")
                    ),
                    payload={
                        "platform": platform,
                        "title": title[:300],
                        "snippet": snippet[:500],
                        "page_age": r.payload.get("age") or r.payload.get("page_age"),
                        "namesake_risk": seed.kind == IdentifierKind.FULL_NAME,
                    },
                    dedupe_key=f"websearch:{_dedupe_url(url)}:{seed.value}",
                    identifier_id=seed.identifier_id,
                )
            )
        return out
