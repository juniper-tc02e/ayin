"""Username Footprint connector (UF3) — self-scan handle-presence discovery.

Sherlock's reach, Ayin's discipline. Sibling of ``broker/detector.py``: probe a
reviewed allowlist of public profile pages for the **requester's own** asserted/
verified username, with robots.txt respected, an identifying UA, gentle pacing,
and per-site error isolation. Honest ``unknown`` verdicts (detection.py) are
dropped, never emitted — so shown findings stay high-precision.

Consent: only ``tos_status==ok`` sites probe (sites_loader.enabled_sites), the
seed handle is checked against the exclude-me list before any probe, and the
SCAN itself is already gated upstream by a verified anchor + the orchestrator's
exclude-me chokepoint. Ownership tier (asserted vs verified) rides in
``seed.context`` and sets confidence + the namesake flag for entity resolution.

NOTE: registered but NOT wired into ``bootstrap`` yet — it stays disabled (no
live probing) until the ER/scoring hooks (UF4) land and counsel signs off.
"""

import logging
import urllib.robotparser
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from ayin.connectors.base import (
    AccessMethod,
    Connector,
    NormalizedFinding,
    RawResult,
    SeedQuery,
    SourceGovernance,
)
from ayin.connectors.registry import registry
from ayin.connectors.username import detection
from ayin.connectors.username.sites_loader import enabled_sites
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

log = logging.getLogger("ayin.connectors.username")

USER_AGENT = "AyinSelfScanBot/0.1 (defensive self-scan of the requester's own handle)"
PROBE_PACING_SECONDS = 0.5

_SENSITIVITY = {
    "low": Sensitivity.LOW,
    "medium": Sensitivity.MEDIUM,
    "high": Sensitivity.HIGH,
    "critical": Sensitivity.CRITICAL,
}
# Ownership tier → base confidence. An asserted handle is "possible — confirm it's
# yours" (a handle can be a namesake); a verified handle is strong.
_OWNERSHIP_CONFIDENCE = {"asserted": 0.5, "verified": 0.85}

# A handle present on ≥ this many sites is itself a cross-account *linkability*
# exposure: reusing one handle lets anyone who finds one account pivot to the rest.
LINKAGE_THRESHOLD = 3


@registry.register
class UsernameFootprintConnector(Connector):
    id = "username_footprint"
    name = "Username Footprint"
    version = "0.1.0"
    governance = SourceGovernance(
        legal_basis=(
            "Self-scan handle-presence: checks whether the verified requester's own "
            "asserted/verified usernames have a public profile on a SMALL, ToS-reviewed "
            "allowlist of sites. Public profile pages only, robots.txt respected, "
            "identifying UA, no login, no resale, no third-party targets (PRD §11.1). "
            "Only sites marked tos_status=ok in sites.yaml are ever probed."
        ),
        access_method=AccessMethod.PUBLIC_PAGE,
        tos_ref="per-site tos_status in ayin/connectors/username/sites.yaml; counsel review pending",
        data_classes=["handle-presence", "profile-url"],
        cost_per_call_usd=0.0,
        rate_limit_per_minute=30,
        counsel_signoff=False,  # stays disabled in prod until reviewed (PRD §11.4)
    )
    supported_kinds = frozenset({IdentifierKind.USERNAME})

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        sites_path: str | None = None,
        exclude_checker: Callable[[str], bool] | None = None,
        **kw,
    ):
        super().__init__(**kw)
        self._transport = transport
        self._sites_path = sites_path
        # Belt-and-suspenders: the orchestrator already drops excluded seeds, but a
        # handle on the exclude-me list must NEVER be probed even if a caller slips
        # it through (blocks "claim someone's handle to scan them"). Default no-op
        # because the orchestrator is the authoritative gate.
        self._exclude_injected = exclude_checker is not None
        self._is_excluded: Callable[[str], bool] = exclude_checker or (lambda _u: False)
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def authenticate(self) -> None:  # public pages — no credentials
        return None

    # ── sensitivity / ownership gate (§6/§10) ────────────────────────
    @staticmethod
    def _is_sensitive(site) -> bool:
        return site.nsfw or site.sensitivity in ("high", "critical")

    @staticmethod
    def _sensitive_allowed(seed: SeedQuery) -> bool:
        """A sensitive (nsfw / high-critical) site only probes for a VERIFIED owner
        who explicitly opted in for this scan. UF5 wires the real verified tier; the
        gate stands now so the safety floor holds by construction, not by manifest
        hygiene — even a row mistakenly marked tos_status=ok stays dark for Tier-0."""
        return (
            seed.context.get("ownership_tier") == "verified"
            and seed.context.get("sensitive_opt_in", "").lower() == "true"
        )

    # ── robots.txt (good citizen; lifted from broker/detector.py) ────
    @staticmethod
    def _deny_all() -> urllib.robotparser.RobotFileParser:
        deny = urllib.robotparser.RobotFileParser()
        deny.parse(["User-agent: *", "Disallow: /"])
        return deny

    def _may_probe(self, client: httpx.Client, url: str) -> bool:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._robots_cache:
            parser = urllib.robotparser.RobotFileParser()
            try:
                res = client.get(f"{host}/robots.txt", headers={"user-agent": USER_AGENT})
            except httpx.HTTPError:
                # Unreachable / malformed / redirect-looping robots → fail SAFE (deny);
                # a broad catch so one host's robots never aborts the whole scan.
                self._robots_cache[host] = self._deny_all()
            else:
                if res.status_code == 200:
                    parser.parse(res.text.splitlines())
                    self._robots_cache[host] = parser
                elif res.status_code in (404, 410):
                    self._robots_cache[host] = None  # truly no robots → allowed
                else:
                    # 401/403/429/5xx and other ambiguous statuses → fail safe / back off
                    self._robots_cache[host] = self._deny_all()
        cached = self._robots_cache[host]
        return True if cached is None else cached.can_fetch(USER_AGENT, url)

    def fetch(self, seed: SeedQuery) -> list[RawResult]:
        if not self._exclude_injected:
            log.warning(
                "username_footprint: no exclude_checker injected — the in-connector "
                "exclude-me gate is a no-op; relying on the orchestrator's upstream "
                "exclusion. Inject a checker before live probing."
            )
        if self._is_excluded(seed.value):
            log.info("username_footprint: seed handle is on the exclude-me list — not probing")
            return []
        sensitive_ok = self._sensitive_allowed(seed)
        now = datetime.now(timezone.utc)
        results: list[RawResult] = []
        with httpx.Client(
            transport=self._transport, timeout=10, follow_redirects=True,
            headers={"user-agent": USER_AGENT},  # identify on EVERY probe, not just robots
        ) as client:
            for site in enabled_sites(self._sites_path):
                if self._is_sensitive(site) and not sensitive_ok:
                    log.info("username_footprint %s: sensitive site needs verified "
                             "ownership + opt-in — skipping", site.id)
                    continue
                url = detection.probe_url(site, seed.value)
                if site.governance.robots_required and not self._may_probe(client, url):
                    log.info("username_footprint %s: robots.txt disallows — skipping", site.id)
                    continue
                try:
                    verdict = detection.classify(site, seed.value, client)
                except Exception as exc:  # noqa: BLE001 — per-site isolation, never fail the run
                    log.warning("username_footprint %s: probe error (%s) — skipping", site.id, exc)
                    verdict = "unknown"
                self._sleep(PROBE_PACING_SECONDS)  # pace between hosts
                if verdict == "present":
                    results.append(
                        RawResult(
                            payload={"site_id": site.id, "profile_url": url},
                            fetched_at=now,
                        )
                    )
        return results

    def normalize(self, seed: SeedQuery, raw: list[RawResult]) -> list[NormalizedFinding]:
        sites = {s.id: s for s in enabled_sites(self._sites_path)}
        raw_tier = seed.context.get("ownership_tier", "asserted")
        # Unknown/garbage tier fails SAFE to asserted, so confidence, namesake_risk
        # and the summary can never disagree (over-claiming "verified" is exactly the
        # false-merge risk FR-ER-1 warns about).
        tier = raw_tier if raw_tier in _OWNERSHIP_CONFIDENCE else "asserted"
        base_conf = _OWNERSHIP_CONFIDENCE[tier]
        out: list[NormalizedFinding] = []
        for r in raw:
            site = sites.get(r.payload.get("site_id", ""))
            if site is None:
                continue
            high = site.sensitivity in ("high", "critical")
            out.append(
                NormalizedFinding(
                    category=FindingCategory.SOCIAL,
                    sensitivity=_SENSITIVITY.get(site.sensitivity, Sensitivity.LOW),
                    source=self.id,
                    source_name=self.name,
                    source_url=r.payload["profile_url"],
                    captured_at=r.fetched_at,
                    confidence=round(base_conf, 2),
                    exploitability=0.4 if high else 0.2,
                    summary=(
                        f"The username “{seed.value}” has a public profile on {site.name}. "
                        + (
                            "Confirm it's yours — a shared handle could be someone else."
                            if tier == "asserted"
                            else "This is one of your verified handles."
                        )
                    ),
                    payload={
                        "site": site.name,
                        "site_id": site.id,
                        "category": site.category,
                        "ownership_tier": tier,
                        # asserted → entity resolution treats it as "possible"
                        "namesake_risk": tier == "asserted",
                        "removable": site.removable,
                        "opt_out_url": site.opt_out.url,
                        "opt_out_instructions": site.opt_out.instructions.strip(),
                        "expected_processing": site.opt_out.expected_processing,
                        "nsfw": site.nsfw,
                    },
                    dedupe_key=f"username_footprint:{site.id}:{seed.value}",
                    identifier_id=seed.identifier_id,
                )
            )

        # Linkage: one handle reused across many sites is its own exposure (it ties
        # the accounts together). Keyed to the same seed → ER caps it to "possible"
        # like every other username finding, so it never silently moves the score.
        if len(out) >= LINKAGE_THRESHOLD:
            site_count = len(out)
            site_names = [str(f.payload.get("site", "")) for f in out if f.payload.get("site")]
            out.append(
                NormalizedFinding(
                    category=FindingCategory.LINKAGE,
                    sensitivity=Sensitivity.HIGH if site_count >= 6 else Sensitivity.MEDIUM,
                    source=self.id,
                    source_name=self.name,
                    source_url=None,
                    captured_at=out[0].captured_at,
                    confidence=round(base_conf, 2),
                    exploitability=0.5,
                    summary=(
                        f"The single handle “{seed.value}” appears on {site_count} of the "
                        "checked sites — reusing one handle lets anyone who finds one of "
                        "your accounts pivot to the rest."
                    ),
                    payload={
                        "kind": "handle_linkage",
                        "handle": seed.value,
                        "site_count": site_count,
                        "sites": site_names[:10],
                        "ownership_tier": tier,
                        "namesake_risk": tier == "asserted",
                    },
                    dedupe_key=f"username_footprint:linkage:{seed.value}",
                    identifier_id=seed.identifier_id,
                )
            )
        return out
