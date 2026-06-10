"""Breach/credential discovery connector — HIBP-class API (FR-DISC-1, M1-2).

Returns *exposure status* only: breach name, date, data classes, and an
exploitability estimate. The upstream API never returns plaintext secrets and
this connector never persists or renders any (FR-DISC-1 / CLAUDE.md).

Config: BREACH_API_KEY (+ optional BREACH_API_BASE_URL). No key → the
connector reports unhealthy and refuses to run (fail closed, no fallback).
Production enablement additionally requires governance counsel sign-off
(PRD §11.4) — flip ``counsel_signoff`` only with the source license recorded.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import quote

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

log = logging.getLogger("ayin.connectors.breach")

_PASSWORD_CLASSES = {"passwords", "password hints", "auth tokens", "historical passwords"}
_HIGH_CLASSES = {
    "phone numbers", "physical addresses", "security questions and answers",
    "government issued ids", "partial credit card data", "social security numbers",
    "dates of birth",
}


def _sensitivity(data_classes: list[str]) -> Sensitivity:
    lowered = {c.lower() for c in data_classes}
    if lowered & _PASSWORD_CLASSES:
        return Sensitivity.CRITICAL
    if lowered & _HIGH_CLASSES:
        return Sensitivity.HIGH
    return Sensitivity.MEDIUM


def _summary(title: str, breach_date: str | None, data_classes: list[str]) -> str:
    dated = f" ({breach_date})" if breach_date else ""
    pw = " including passwords" if _sensitivity(data_classes) == Sensitivity.CRITICAL else ""
    return (
        f"This email appears in the '{title}' breach{dated}, which exposed "
        f"{len(data_classes)} data class(es){pw}. "
        "Exposure status only — no secret is stored or shown."
    )


def _exploitability(data_classes: list[str], breach_date: str | None) -> float:
    lowered = {c.lower() for c in data_classes}
    score = 0.3
    if lowered & _PASSWORD_CLASSES:
        score = 0.85
    elif lowered & _HIGH_CLASSES:
        score = 0.6
    if breach_date:
        try:
            year = int(breach_date[:4])
            if datetime.now(timezone.utc).year - year <= 2:
                score = min(0.95, score + 0.1)  # fresher creds are likelier still live
        except ValueError:
            pass
    return round(score, 2)


@registry.register
class BreachConnector(Connector):
    id = "breach_hibp"
    name = "Have I Been Pwned"
    version = "0.1.0"
    governance = SourceGovernance(
        legal_basis=(
            "Licensed breach-notification API (HIBP-class). Returns breach metadata "
            "and exposure status for an identifier the requester has verified they "
            "control; never plaintext credentials. No purchased dumps (PRD §11.1)."
        ),
        access_method=AccessMethod.LICENSED_API,
        tos_ref="https://haveibeenpwned.com/API/v3#License",
        data_classes=[
            "breach-name", "breach-date", "breach-domain",
            "exposed-data-classes", "verification-status", "pwn-count",
        ],
        cost_per_call_usd=0.001,  # entry subscription amortized; telemetry refines
        rate_limit_per_minute=10,  # entry-tier RPM
        counsel_signoff=False,  # flip only with license + counsel record (PRD §11.4)
    )
    supported_kinds = frozenset({IdentifierKind.EMAIL})

    def __init__(self, *, transport: httpx.BaseTransport | None = None, **kw):
        super().__init__(**kw)
        settings = get_settings()
        self._api_key = settings.breach_api_key
        self._base = settings.breach_api_base_url.rstrip("/")
        self._transport = transport

    def authenticate(self) -> None:
        if not self._api_key:
            raise ConnectorAuthError(
                "breach connector: BREACH_API_KEY not configured — refusing to run"
            )

    def fetch(self, seed: SeedQuery) -> list[RawResult]:
        url = f"{self._base}/breachedaccount/{quote(seed.value)}"
        headers = {
            "hibp-api-key": self._api_key,
            "user-agent": "Ayin-SelfScan/0.1 (defensive self-exposure scan)",
        }
        with httpx.Client(transport=self._transport, timeout=15) as client:
            try:
                res = client.get(url, headers=headers, params={"truncateResponse": "false"})
            except httpx.TransportError as exc:
                raise ConnectorTransientError(f"breach API unreachable: {exc}") from exc
        if res.status_code == 404:
            return []  # not found in any breach — a *good* result
        if res.status_code in (401, 403):
            raise ConnectorAuthError(f"breach API rejected credentials ({res.status_code})")
        if res.status_code == 429 or res.status_code >= 500:
            raise ConnectorTransientError(f"breach API throttled/unavailable ({res.status_code})")
        if res.status_code != 200:
            raise ConnectorPermanentError(f"breach API unexpected status {res.status_code}")
        now = datetime.now(timezone.utc)
        return [RawResult(payload=b, fetched_at=now) for b in res.json()]

    def normalize(self, seed: SeedQuery, raw: list[RawResult]) -> list[NormalizedFinding]:
        out = []
        for r in raw:
            b = r.payload
            name = str(b.get("Name", "")).strip()
            if not name:
                continue  # untrusted input: skip malformed entries
            data_classes = [str(c) for c in b.get("DataClasses", [])]
            breach_date = b.get("BreachDate")
            title = str(b.get("Title", name))
            out.append(
                NormalizedFinding(
                    category=FindingCategory.CREDENTIAL,
                    sensitivity=_sensitivity(data_classes),
                    source=self.id,
                    source_name=self.name,
                    source_url=f"https://haveibeenpwned.com/breach/{quote(name)}",
                    captured_at=r.fetched_at,
                    confidence=0.95 if b.get("IsVerified", False) else 0.75,
                    exploitability=_exploitability(data_classes, breach_date),
                    summary=_summary(title, breach_date, data_classes),
                    payload={
                        "breach_name": name,
                        "title": title,
                        "domain": b.get("Domain"),
                        "breach_date": breach_date,
                        "data_classes": data_classes,
                        "is_verified": bool(b.get("IsVerified", False)),
                        "pwn_count": b.get("PwnCount"),
                    },
                    dedupe_key=f"hibp:{name}:{seed.value}",
                    identifier_id=seed.identifier_id,
                )
            )
        return out
