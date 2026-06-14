"""M0-7 acceptance: the connector contract.

- FakeConnector runs through the contract and emits normalized findings
  with full attribution
- a connector cannot be registered without a complete governance block
- production enablement requires counsel sign-off
- rate limit, backoff/retry, cost telemetry, and output validation behave
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ayin.connectors import (
    AccessMethod,
    Connector,
    ConnectorCapability,
    ConnectorContractViolation,
    ConnectorRateLimited,
    ConnectorRegistry,
    ConnectorTransientError,
    LatencyClass,
    NormalizedFinding,
    RawResult,
    SeedQuery,
    SourceGovernance,
)
from ayin.connectors.fake import FakeConnector
from ayin.connectors.registry import RegistrationError
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity

GOOD_GOVERNANCE = SourceGovernance(
    legal_basis="Synthetic fixture data for tests; nothing external.",
    access_method=AccessMethod.SYNTHETIC,
    tos_ref="n/a",
    data_classes=["fixture"],
    cost_per_call_usd=0.25,
    rate_limit_per_minute=2,
    counsel_signoff=False,
)

EMAIL_SEED = SeedQuery(kind=IdentifierKind.EMAIL, value="fixture@example.org")


class MiniConnector(Connector):
    """Minimal compliant connector used to exercise contract mechanics."""

    id = "mini"
    name = "Mini (test)"
    version = "0.0.1"
    governance = GOOD_GOVERNANCE
    supported_kinds = frozenset({IdentifierKind.EMAIL})
    capability = ConnectorCapability(
        output_categories=frozenset({FindingCategory.SOCIAL}),
        latency_class=LatencyClass.FAST,
        description="Minimal compliant connector for contract tests.",
    )

    def __init__(self, fail_times=0, emit=None, **kw):
        super().__init__(**kw)
        self.fail_times = fail_times
        self.emit = emit

    def authenticate(self) -> None:
        return None

    def fetch(self, seed):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectorTransientError("fixture blip")
        return [RawResult(payload={}, fetched_at=datetime.now(timezone.utc))]

    def normalize(self, seed, raw):
        if self.emit is not None:
            return self.emit
        return [
            NormalizedFinding(
                category=FindingCategory.SOCIAL,
                sensitivity=Sensitivity.LOW,
                source=self.id,
                source_name=self.name,
                captured_at=datetime.now(timezone.utc),
                confidence=0.5,
                summary="(FAKE) minimal fixture finding",
                dedupe_key=f"mini:{seed.value}",
            )
        ]


# ── Governance enforcement ───────────────────────────────────────────


def test_governance_block_cannot_be_incomplete():
    with pytest.raises(ValidationError):
        SourceGovernance(  # type: ignore[call-arg]
            legal_basis="Synthetic fixture data for tests.",
            access_method=AccessMethod.SYNTHETIC,
            tos_ref="n/a",
            data_classes=["fixture"],
            # cost_per_call_usd missing
            rate_limit_per_minute=10,
            counsel_signoff=True,
        )


def test_registry_rejects_connector_without_governance():
    reg = ConnectorRegistry()

    class NoGov(Connector):
        id = "nogov"
        name = "No Governance"
        version = "0.0.1"
        governance = None  # type: ignore[assignment]
        supported_kinds = frozenset({IdentifierKind.EMAIL})

        def authenticate(self): ...
        def fetch(self, seed): return []
        def normalize(self, seed, raw): return []

    with pytest.raises(RegistrationError):
        reg.register(NoGov)


def test_registry_rejects_connector_without_capability():
    reg = ConnectorRegistry()

    class NoCap(Connector):
        id = "nocap"
        name = "No Capability"
        version = "0.0.1"
        governance = GOOD_GOVERNANCE
        supported_kinds = frozenset({IdentifierKind.EMAIL})
        # capability deliberately omitted — S1-1 makes the manifest mandatory.

        def authenticate(self): ...
        def fetch(self, seed): return []
        def normalize(self, seed, raw): return []

    with pytest.raises(RegistrationError):
        reg.register(NoCap)


def test_registry_rejects_duplicate_ids():
    reg = ConnectorRegistry()
    reg.register(MiniConnector)
    with pytest.raises(RegistrationError):
        reg.register(MiniConnector)


def test_production_enable_requires_counsel_signoff():
    reg = ConnectorRegistry()
    reg.register(MiniConnector)  # counsel_signoff=False
    reg.enable("mini", environment="development")  # fine locally
    assert reg.is_enabled("mini")
    reg.disable("mini")
    with pytest.raises(RegistrationError):
        reg.enable("mini", environment="production")


# ── FakeConnector through the full contract ──────────────────────────


def test_fake_connector_emits_fully_attributed_findings():
    run = FakeConnector().run(EMAIL_SEED)
    assert len(run.findings) == 2  # fake breach + fake broker listing
    for f in run.findings:
        assert f.source == "fake"
        assert f.source_name
        assert f.captured_at.tzinfo is not None
        assert 0.0 <= f.confidence <= 1.0
        assert f.sensitivity in set(Sensitivity)
        assert f.category in set(FindingCategory)
        assert f.summary and f.dedupe_key
    cats = {f.category for f in run.findings}
    assert cats == {FindingCategory.CREDENTIAL, FindingCategory.BROKER}
    assert run.telemetry.calls == 1
    assert run.telemetry.cost_usd == 0.0


def test_fake_connector_never_emits_plaintext_secrets():
    """FR-DISC-1 posture starts at the fixture: exposure status only."""
    run = FakeConnector().run(EMAIL_SEED)
    breach = next(f for f in run.findings if f.category == FindingCategory.CREDENTIAL)
    blob = (str(breach.payload) + breach.summary).lower()
    assert "password-hash" in blob  # data class label is fine
    assert "hunter2" not in blob  # no literal secrets anywhere
    assert breach.sensitive_payload is None


def test_unsupported_kind_returns_empty_not_error():
    run = FakeConnector().run(SeedQuery(kind=IdentifierKind.CITY, value="faketown"))
    assert run.findings == []


# ── Contract mechanics ───────────────────────────────────────────────


def test_rate_limit_budget_enforced():
    t = [0.0]
    c = MiniConnector(clock=lambda: t[0], sleep=lambda s: None)  # 2/minute budget
    c.run(EMAIL_SEED)
    c.run(EMAIL_SEED)
    with pytest.raises(ConnectorRateLimited):
        c.run(EMAIL_SEED)
    t[0] += 31.0  # half a minute refills one token
    assert c.run(EMAIL_SEED).findings


def test_transient_failures_are_retried_with_backoff():
    slept = []
    c = MiniConnector(fail_times=2, sleep=slept.append)
    run = c.run(EMAIL_SEED)
    assert len(run.findings) == 1
    assert run.telemetry.calls == 3
    assert run.telemetry.retries == 2
    assert len(slept) == 2
    assert slept[1] > 0  # backed off, with jitter


def test_permanent_failure_after_max_retries():
    c = MiniConnector(fail_times=99, sleep=lambda s: None)
    with pytest.raises(ConnectorTransientError):
        c.run(EMAIL_SEED)
    # 1 initial + MAX_RETRIES attempts were paid for
    assert c.fail_times == 99 - 4


def test_cost_telemetry_accumulates_per_call():
    c = MiniConnector(fail_times=1, sleep=lambda s: None)
    run = c.run(EMAIL_SEED)
    assert run.telemetry.calls == 2
    assert run.telemetry.cost_usd == pytest.approx(0.50)


def test_connector_cannot_spoof_another_source():
    forged = NormalizedFinding(
        category=FindingCategory.SOCIAL,
        sensitivity=Sensitivity.LOW,
        source="someone-else",
        source_name="Forged",
        captured_at=datetime.now(timezone.utc),
        confidence=0.5,
        summary="(FAKE) forged-source finding",
        dedupe_key="forged:1",
    )
    c = MiniConnector(emit=[forged])
    with pytest.raises(ConnectorContractViolation):
        c.run(EMAIL_SEED)


def test_findings_require_attribution_fields():
    with pytest.raises(ValidationError):
        NormalizedFinding(  # type: ignore[call-arg]
            category=FindingCategory.SOCIAL,
            sensitivity=Sensitivity.LOW,
            source="mini",
            source_name="Mini (test)",
            # captured_at missing
            confidence=0.5,
            summary="x",
            dedupe_key="k",
        )
    with pytest.raises(ValidationError):  # naive datetime rejected
        NormalizedFinding(
            category=FindingCategory.SOCIAL,
            sensitivity=Sensitivity.LOW,
            source="mini",
            source_name="Mini (test)",
            captured_at=datetime(2026, 1, 1),
            confidence=0.5,
            summary="x",
            dedupe_key="k",
        )
