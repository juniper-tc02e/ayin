"""Data-broker detection connector (FR-DISC-3, M1-4) — detect to remove.

For each registry broker with probing enabled, fetch the public listing-search
page for the subject's name (+city) and look for listing markers. Properties:

- **Public pages only**, robots.txt respected per host, identifying UA, gentle
  pacing between probes. A broker we may not probe is skipped, not forced.
- **Detect only** — no removal automation in MVP. Every detection carries the
  registry's manual opt-out URL + instructions + expected processing time.
- **Namesake honesty**: detections are name-keyed → moderate confidence,
  flagged for user confirmation (ER lands in M2).
- A single broken broker site never fails the whole job (per-broker errors
  are recorded and skipped).

Per-run pacing note: the contract's token bucket is per run(); within a run
this connector paces sequential probes itself via the injectable sleep.
"""

import logging
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import httpx

from ayin.config import get_settings
from ayin.connectors.base import (
    AccessMethod,
    Connector,
    NormalizedFinding,
    RawResult,
    SeedQuery,
    SourceGovernance,
)
from ayin.connectors.broker.registry_loader import BrokerEntry, load_registry
from ayin.connectors.registry import registry
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

log = logging.getLogger("ayin.connectors.broker")

USER_AGENT = "AyinSelfScanBot/0.1 (defensive self-scan on the subject's own behalf)"
_HIGH_EXPOSURE_FIELDS = {"address", "phone", "relatives", "criminal_records", "ip_addresses"}
PROBE_PACING_SECONDS = 0.5


def _name_parts(value: str, context: dict[str, str]) -> dict[str, str]:
    tokens = [t for t in value.strip().split() if t]
    first = tokens[0] if tokens else ""
    last = tokens[-1] if len(tokens) > 1 else ""
    city = context.get("city", "")
    return {
        "first": quote(first),
        "last": quote(last),
        "name_dashed": quote("-".join(tokens)),
        "city_dashed": quote("-".join(city.split())) if city else "",
    }


@registry.register
class BrokerDetectionConnector(Connector):
    id = "broker_detect"
    name = "Data Broker Detection"
    version = "0.1.0"
    governance = SourceGovernance(
        legal_basis=(
            "Detection-to-remove: checks whether the verified requester's own "
            "name appears on public people-search listing pages, to drive their "
            "opt-out. Public pages only, robots.txt respected, identifying UA, "
            "no login, no resale (PRD §11.1, §11.2 row C)."
        ),
        access_method=AccessMethod.PUBLIC_PAGE,
        tos_ref="per-broker registry rows (registry.yaml); counsel review pending",
        data_classes=["listing-presence", "listing-url", "exposed-field-categories"],
        cost_per_call_usd=0.0,
        rate_limit_per_minute=30,
        counsel_signoff=False,  # per-broker verification + counsel before live probing
    )
    supported_kinds = frozenset({IdentifierKind.FULL_NAME})

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        registry_path: str | None = None,
        **kw,
    ):
        super().__init__(**kw)
        self._transport = transport
        self._registry_path = registry_path or get_settings().broker_registry_path
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def authenticate(self) -> None:  # no credentials — public pages
        return None

    # ── robots.txt (good citizen) ────────────────────────────────────
    def _may_probe(self, client: httpx.Client, url: str) -> bool:
        host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if host not in self._robots_cache:
            parser = urllib.robotparser.RobotFileParser()
            try:
                res = client.get(f"{host}/robots.txt", headers={"user-agent": USER_AGENT})
                if res.status_code == 200:
                    parser.parse(res.text.splitlines())
                    self._robots_cache[host] = parser
                else:
                    self._robots_cache[host] = None  # no robots → allowed
            except httpx.TransportError:
                self._robots_cache[host] = parser_deny = urllib.robotparser.RobotFileParser()
                parser_deny.parse(["User-agent: *", "Disallow: /"])  # unreachable → be safe
        cached = self._robots_cache[host]
        return True if cached is None else cached.can_fetch(USER_AGENT, url)

    def fetch(self, seed: SeedQuery) -> list[RawResult]:
        reg = load_registry(self._registry_path)
        parts = _name_parts(seed.value, seed.context)
        now = datetime.now(timezone.utc)
        results: list[RawResult] = []
        with httpx.Client(
            transport=self._transport, timeout=10, follow_redirects=True
        ) as client:
            for broker in reg.brokers:
                if not broker.probe.enabled:
                    continue
                url = broker.probe.url_template.format(**parts)
                if not self._may_probe(client, url):
                    log.info("broker %s: robots.txt disallows %s — skipping", broker.id, url)
                    continue
                try:
                    res = client.get(url, headers={"user-agent": USER_AGENT})
                except httpx.TransportError as exc:
                    log.warning("broker %s unreachable (%s) — skipping", broker.id, exc)
                    continue
                self._sleep(PROBE_PACING_SECONDS)  # pace between hosts
                if res.status_code != 200:
                    continue
                text = res.text.lower()
                if any(m.lower() in text for m in broker.probe.notfound_markers):
                    continue
                if any(m.lower() in text for m in broker.probe.found_markers):
                    results.append(
                        RawResult(
                            payload={"broker_id": broker.id, "probe_url": url},
                            fetched_at=now,
                        )
                    )
        return results

    def normalize(self, seed: SeedQuery, raw: list[RawResult]) -> list[NormalizedFinding]:
        reg = load_registry(self._registry_path)
        by_id: dict[str, BrokerEntry] = {b.id: b for b in reg.brokers}
        out = []
        for r in raw:
            broker = by_id.get(r.payload.get("broker_id", ""))
            if broker is None:
                continue
            high = bool(set(broker.exposed_fields) & _HIGH_EXPOSURE_FIELDS)
            out.append(
                NormalizedFinding(
                    category=FindingCategory.BROKER,
                    sensitivity=Sensitivity.HIGH if high else Sensitivity.MEDIUM,
                    source=self.id,
                    source_name=self.name,
                    source_url=r.payload["probe_url"],
                    captured_at=r.fetched_at,
                    confidence=0.6,  # name-keyed: needs user confirmation (M2 ER)
                    exploitability=0.5 if high else 0.3,
                    summary=(
                        f"A listing matching this name appears on {broker.name} — "
                        f"typically exposing {', '.join(broker.exposed_fields[:4])}. "
                        "It can be removed with a manual opt-out (instructions attached)."
                    ),
                    payload={
                        "site": broker.name,
                        "broker_id": broker.id,
                        "family": broker.family,
                        "exposed_fields": broker.exposed_fields,
                        "removable": True,
                        "opt_out_url": broker.opt_out.url,
                        "opt_out_instructions": broker.opt_out.instructions.strip(),
                        "expected_processing": broker.opt_out.expected_processing,
                        "namesake_risk": True,
                    },
                    dedupe_key=f"broker:{broker.id}:{seed.value}",
                    identifier_id=seed.identifier_id,
                )
            )
        return out
