"""S1-2 acceptance: jurisdiction + legal-basis routing.

A source declares the jurisdictions where it is lawful to use
(``SourceGovernance.lawful_jurisdictions``); a subject's jurisdiction is
inferred from its seeds. A US-only source is never proposed for an EU-only
subject, while an unknown subject jurisdiction stays permissive (inference is
future work). The routing decision is recorded on the ``scan.started`` audit
event.

All data clearly fake.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select

from ayin.config import get_settings
from ayin.connectors import (
    GLOBAL_JURISDICTION,
    AccessMethod,
    ConnectorRegistry,
    SourceGovernance,
)
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord, Identifier, Scan, Subject, User
from ayin.models.enums import IdentifierKind, VerificationState
from ayin.orchestrator import engine
from ayin.orchestrator.engine import subject_jurisdictions
from ayin.vault import NullVault

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _gov(**over):
    base = dict(
        legal_basis="Synthetic fixture data for jurisdiction tests.",
        access_method=AccessMethod.SYNTHETIC,
        tos_ref="n/a",
        data_classes=["fixture"],
        cost_per_call_usd=0.0,
        rate_limit_per_minute=600,
        counsel_signoff=True,
    )
    base.update(over)
    return SourceGovernance(**base)


# ── Unit: the lawful-use rule ────────────────────────────────────────


def test_global_source_is_lawful_everywhere():
    gov = _gov()  # default lawful_jurisdictions = {"*"}
    assert GLOBAL_JURISDICTION in gov.lawful_jurisdictions
    assert gov.lawful_for(frozenset())             # unknown subject
    assert gov.lawful_for(frozenset({"US"}))
    assert gov.lawful_for(frozenset({"DE"}))


def test_us_only_source_never_lawful_for_eu_subject():
    gov = _gov(lawful_jurisdictions=frozenset({"US"}))
    assert gov.lawful_for(frozenset({"US"})) is True
    assert gov.lawful_for(frozenset({"DE"})) is False        # the EU rule
    assert gov.lawful_for(frozenset({"DE", "US"})) is True   # one match suffices


def test_unknown_subject_jurisdiction_is_permissive():
    gov = _gov(lawful_jurisdictions=frozenset({"US"}))
    assert gov.lawful_for(frozenset()) is True  # not yet inferred → not restricted


def test_lawful_jurisdictions_are_normalized_uppercase():
    gov = _gov(lawful_jurisdictions=frozenset({"us", " gb "}))
    assert gov.lawful_jurisdictions == frozenset({"US", "GB"})


def test_subject_jurisdictions_dedupes_and_uppercases():
    seeds = [
        SimpleNamespace(jurisdiction="us"),
        SimpleNamespace(jurisdiction="DE"),
        SimpleNamespace(jurisdiction=None),
        SimpleNamespace(jurisdiction="  "),
        SimpleNamespace(jurisdiction="us"),
    ]
    assert subject_jurisdictions(seeds) == frozenset({"US", "DE"})


# ── Integration: routing through the live dispatch path ──────────────


class USOnlyConnector(FakeConnector):
    id = "us_only"
    name = "US-only fixture source"
    governance = _gov(lawful_jurisdictions=frozenset({"US"}))

    def normalize(self, seed, raw):
        return []  # emits nothing — we only care whether it is dispatched


def _registry():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)        # global (default lawful everywhere)
    reg.register(USOnlyConnector)      # US-only
    reg.enable("fake", environment="test")
    reg.enable("us_only", environment="test")
    return reg


def _subject_with_email(db, *, jurisdiction):
    u = User(email=f"jx-{uuid.uuid4().hex[:8]}@example.org")
    db.add(u)
    db.flush()
    s = Subject(owner_user_id=u.id)
    db.add(s)
    db.flush()
    db.add(
        Identifier(
            subject_id=s.id, kind=IdentifierKind.EMAIL,
            value_raw=u.email, value_normalized=u.email,
            verification_state=VerificationState.VERIFIED, verified_at=NOW,
            jurisdiction=jurisdiction,
        )
    )
    db.flush()
    db.commit()
    return u


def _run(db, user):
    scan, result = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=_registry(),
        vault=NullVault(), inline=True,
    )
    db.expire_all()
    return db.get(Scan, scan.id), result


def test_us_only_source_not_dispatched_for_eu_subject(db):
    scan, result = _run(db, _subject_with_email(db, jurisdiction="DE"))
    assert result.passed
    assert "us_only" not in scan.source_set   # never proposed — the acceptance
    assert "fake" in scan.source_set          # the global source still runs
    # The routing decision is recorded on the audit trail.
    started = db.execute(
        select(AuditRecord).where(
            AuditRecord.scan_id == scan.id, AuditRecord.event_type == "scan.started"
        )
    ).scalar_one()
    assert started.detail.get("jurisdiction_skipped") == ["us_only"]
    assert started.detail.get("subject_jurisdictions") == ["DE"]


def test_us_only_source_dispatched_for_us_subject(db):
    scan, _ = _run(db, _subject_with_email(db, jurisdiction="US"))
    assert "us_only" in scan.source_set


def test_unknown_jurisdiction_stays_permissive(db):
    scan, _ = _run(db, _subject_with_email(db, jurisdiction=None))
    assert "us_only" in scan.source_set  # not inferred → not restricted
