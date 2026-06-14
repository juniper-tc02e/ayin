"""FakeConnector — proves the contract end-to-end with clearly-fake data.

Never returns real data; every value is an obvious fixture. Used by tests and
by local development until the real breach/search/broker connectors (M1-2..4)
land.
"""

from datetime import datetime, timezone

from ayin.connectors.base import (
    AccessMethod,
    Connector,
    ConnectorCapability,
    LatencyClass,
    NormalizedFinding,
    RawResult,
    SeedQuery,
    SourceGovernance,
)
from ayin.connectors.registry import registry
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity


@registry.register
class FakeConnector(Connector):
    id = "fake"
    name = "Fake Source (synthetic fixtures)"
    version = "0.1.0"
    governance = SourceGovernance(
        legal_basis="Synthetic fixture data generated in-process; no external source.",
        access_method=AccessMethod.SYNTHETIC,
        tos_ref="n/a (synthetic)",
        data_classes=["breach-exposure (fake)", "broker-listing (fake)", "profile (fake)"],
        cost_per_call_usd=0.0,
        rate_limit_per_minute=60,
        counsel_signoff=True,  # nothing external to review
    )
    supported_kinds = frozenset(
        {IdentifierKind.EMAIL, IdentifierKind.USERNAME, IdentifierKind.PHONE}
    )
    capability = ConnectorCapability(
        output_categories=frozenset(
            {FindingCategory.CREDENTIAL, FindingCategory.BROKER, FindingCategory.SOCIAL}
        ),
        context_used=frozenset(),
        latency_class=LatencyClass.FAST,
        description="Synthetic fixtures exercising the full contract (tests and local dev only).",
    )

    def authenticate(self) -> None:  # no credentials needed
        return None

    def fetch(self, seed: SeedQuery) -> list[RawResult]:
        now = datetime.now(timezone.utc)
        payloads: list[dict]
        if seed.kind == IdentifierKind.EMAIL:
            payloads = [
                {"type": "breach", "name": "ExampleBreach-2024 (FAKE)",
                 "breached_on": "2024-03-01", "classes": ["email", "password-hash"]},
                {"type": "broker", "site": "fake-people-search.example",
                 "url": f"https://fake-people-search.example/listing/{seed.value}"},
            ]
        elif seed.kind == IdentifierKind.USERNAME:
            payloads = [
                {"type": "profile", "platform": "example-social",
                 "url": f"https://social.example/@{seed.value}"},
            ]
        else:
            payloads = []
        return [RawResult(payload=p, fetched_at=now) for p in payloads]

    def normalize(self, seed: SeedQuery, raw: list[RawResult]) -> list[NormalizedFinding]:
        out: list[NormalizedFinding] = []
        for r in raw:
            p = r.payload
            if p["type"] == "breach":
                out.append(
                    NormalizedFinding(
                        category=FindingCategory.CREDENTIAL,
                        sensitivity=Sensitivity.HIGH,
                        source=self.id,
                        source_name=self.name,
                        captured_at=r.fetched_at,
                        confidence=0.95,
                        exploitability=0.7,
                        summary=f"(FAKE) {seed.value} appears in the fixture breach "
                                f"'{p['name']}' — exposure status only, no secrets.",
                        payload={"breach_name": p["name"], "breached_on": p["breached_on"],
                                 "data_classes": p["classes"]},
                        dedupe_key=f"fake:breach:{p['name']}:{seed.value}",
                        identifier_id=seed.identifier_id,
                    )
                )
            elif p["type"] == "broker":
                out.append(
                    NormalizedFinding(
                        category=FindingCategory.BROKER,
                        sensitivity=Sensitivity.MEDIUM,
                        source=self.id,
                        source_name=self.name,
                        source_url=p["url"],
                        captured_at=r.fetched_at,
                        confidence=0.9,
                        summary=f"(FAKE) A fixture broker listing for {seed.value} on "
                                f"{p['site']} — flagged removable.",
                        # Mirrors the real broker connector's payload shape
                        # (ayin.connectors.broker.detector) so the opt-out
                        # flow — checklist steps + the report's removal link —
                        # exercises the same fields end to end.
                        payload={
                            "site": p["site"],
                            "removable": True,
                            "opt_out_url": "https://fake-people-search.example/opt-out",
                            "opt_out_instructions": "Open the opt-out page, find your "
                            "listing, and submit the removal request for your email.",
                            "expected_processing": "a few days",
                        },
                        dedupe_key=f"fake:broker:{p['site']}:{seed.value}",
                        identifier_id=seed.identifier_id,
                    )
                )
            elif p["type"] == "profile":
                out.append(
                    NormalizedFinding(
                        category=FindingCategory.SOCIAL,
                        sensitivity=Sensitivity.LOW,
                        source=self.id,
                        source_name=self.name,
                        source_url=p["url"],
                        captured_at=r.fetched_at,
                        confidence=0.8,
                        summary=f"(FAKE) Public fixture profile '@{seed.value}' on "
                                f"{p['platform']}.",
                        payload={"platform": p["platform"]},
                        dedupe_key=f"fake:profile:{p['platform']}:{seed.value}",
                        identifier_id=seed.identifier_id,
                    )
                )
        return out
