"""M1-1 acceptance: scan state machine.

- a scan fans out to connectors and records status transitions (audited)
- gates refuse before any connector runs (no verified anchor / excluded)
- partial results persist; a failed connector doesn't void the others
- a scan survives a worker "restart" mid-run (resume_stalled)
- job re-runs are idempotent (no duplicate findings)

All data clearly fake.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from ayin.config import get_settings
from ayin.connectors import (
    AccessMethod,
    Connector,
    ConnectorPermanentError,
    ConnectorRegistry,
    ConnectorTransientError,
    NormalizedFinding,
    RawResult,
    SourceGovernance,
)
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord, ConnectorJob, Finding, Identifier, Scan, Subject, User
from ayin.models.enums import (
    FindingCategory,
    IdentifierKind,
    JobStatus,
    ScanStatus,
    Sensitivity,
    VerificationState,
)
from ayin.orchestrator import engine
from ayin.vault import NullVault

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _gov(**over):
    base = dict(
        legal_basis="Synthetic fixture data for orchestrator tests.",
        access_method=AccessMethod.SYNTHETIC,
        tos_ref="n/a",
        data_classes=["fixture"],
        cost_per_call_usd=0.0,
        rate_limit_per_minute=600,
        counsel_signoff=False,
    )
    base.update(over)
    return SourceGovernance(**base)


class SecondConnector(Connector):
    """A second fixture source so scans have two jobs."""

    id = "second"
    name = "Second Fixture Source"
    version = "0.0.1"
    governance = _gov()
    supported_kinds = frozenset({IdentifierKind.EMAIL})

    def authenticate(self): ...

    def fetch(self, seed):
        return [RawResult(payload={}, fetched_at=datetime.now(timezone.utc))]

    def normalize(self, seed, raw):
        return [
            NormalizedFinding(
                category=FindingCategory.SOCIAL,
                sensitivity=Sensitivity.LOW,
                source=self.id,
                source_name=self.name,
                captured_at=datetime.now(timezone.utc),
                confidence=0.6,
                summary="(FAKE) second-source fixture finding",
                dedupe_key=f"second:{seed.value}",
                identifier_id=seed.identifier_id,
            )
        ]


class BrokenConnector(SecondConnector):
    id = "broken"
    name = "Broken Fixture Source"
    governance = _gov()

    def fetch(self, seed):
        raise ConnectorPermanentError("fixture: source contract changed")


class FlakyConnector(SecondConnector):
    id = "flaky"
    name = "Flaky Fixture Source"
    governance = _gov()
    fail_budget = {"n": 0}  # class-level so fresh instances share the budget

    def fetch(self, seed):
        if self.fail_budget["n"] > 0:
            self.fail_budget["n"] -= 1
            raise ConnectorTransientError("fixture blip")
        return super().fetch(seed)


@pytest.fixture()
def registry():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.register(SecondConnector)
    reg.enable("fake", environment="test")
    reg.enable("second", environment="test")
    return reg


@pytest.fixture()
def vault():
    return NullVault()


@pytest.fixture()
def settings():
    return get_settings()


def _mk_user(db, *, verified=True, with_aux=True) -> User:
    u = User(email=f"orch-{uuid.uuid4().hex[:8]}@example.org")
    db.add(u)
    db.flush()
    s = Subject(owner_user_id=u.id)
    db.add(s)
    db.flush()
    email = Identifier(
        subject_id=s.id,
        kind=IdentifierKind.EMAIL,
        value_raw=u.email,
        value_normalized=u.email,
        verification_state=(
            VerificationState.VERIFIED if verified else VerificationState.UNVERIFIED
        ),
        verified_at=NOW if verified else None,
    )
    db.add(email)
    if with_aux:
        db.add(
            Identifier(
                subject_id=s.id, kind=IdentifierKind.USERNAME,
                value_raw="fake_handle", value_normalized="fake_handle",
            )
        )
    db.flush()
    db.commit()
    return u


def _events(db, scan_id):
    return db.execute(
        select(AuditRecord.event_type)
        .where(AuditRecord.scan_id == scan_id)
        .order_by(AuditRecord.id)
    ).scalars().all()


def test_full_pipeline_inline(db, registry, vault, settings):
    user = _mk_user(db)
    scan, result = engine.start_scan(
        db, requester=user, settings=settings, registry=registry, vault=vault, inline=True
    )
    assert result.passed
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan.status == ScanStatus.DONE
    assert scan.error is None
    assert sorted(scan.source_set) == ["fake", "second"]

    jobs = db.execute(select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)).scalars().all()
    assert {j.status for j in jobs} == {JobStatus.DONE}

    findings = db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalars().all()
    # fake: breach+broker for email, profile for username; second: 1 for email
    assert len(findings) == 4
    assert all(f.source and f.captured_at and f.confidence is not None for f in findings)

    events = _events(db, scan.id)
    for expected in ["scan.created", "scan.gated", "scan.started",
                     "scan.connector_finished", "scan.resolving", "scan.scoring",
                     "scan.completed"]:
        assert expected in events, expected
    # status transitions recorded in order
    order = [events.index(e) for e in ("scan.gated", "scan.started", "scan.completed")]
    assert order == sorted(order)


def test_gate_refuses_without_verified_anchor(db, registry, vault, settings):
    user = _mk_user(db, verified=False)  # email present but unverified
    scan, result = engine.start_scan(
        db, requester=user, settings=settings, registry=registry, vault=vault, inline=True
    )
    assert not result.passed
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan.status == ScanStatus.FAILED
    assert "no_verified_anchor" in scan.error
    assert db.execute(
        select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)
    ).first() is None  # nothing dispatched — gate is in the critical path
    assert "scan.refused" in _events(db, scan.id)


def test_gate_refuses_excluded_subject(db, registry, vault, settings):
    user = _mk_user(db)
    subject = db.execute(select(Subject).where(Subject.owner_user_id == user.id)).scalar_one()
    subject.exclusion_state = "excluded"
    db.commit()
    scan, result = engine.start_scan(
        db, requester=user, settings=settings, registry=registry, vault=vault, inline=True
    )
    assert not result.passed
    db.expire_all()
    assert db.get(Scan, scan.id).error == "subject_excluded"


def test_unverified_challengeable_seed_never_fans_out(db, registry, vault, settings):
    """A second, UNVERIFIED email must not be scanned: control unproven."""
    user = _mk_user(db)
    subject = db.execute(select(Subject).where(Subject.owner_user_id == user.id)).scalar_one()
    unverified = Identifier(
        subject_id=subject.id, kind=IdentifierKind.EMAIL,
        value_raw="unproven@example.org", value_normalized="unproven@example.org",
    )
    db.add(unverified)
    db.commit()

    scan, _ = engine.start_scan(
        db, requester=user, settings=settings, registry=registry, vault=vault, inline=True
    )
    findings = db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalars().all()
    assert findings
    assert all(f.identifier_id != unverified.id for f in findings)
    assert all("unproven@example.org" not in (f.summary + str(f.payload)) for f in findings)


def test_partial_results_when_one_connector_fails(db, vault, settings):
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.register(BrokenConnector)
    reg.enable("fake", environment="test")
    reg.enable("broken", environment="test")

    user = _mk_user(db)
    scan, _ = engine.start_scan(
        db, requester=user, settings=settings, registry=reg, vault=vault, inline=True
    )
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan.status == ScanStatus.DONE  # partial results stand
    assert "broken" in scan.error
    findings = db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalars().all()
    assert len(findings) == 3  # fake's findings persisted despite broken failing
    jobs = {j.connector_id: j for j in db.execute(
        select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)
    ).scalars()}
    assert jobs["broken"].status == JobStatus.FAILED
    assert jobs["fake"].status == JobStatus.DONE
    assert "scan.connector_failed" in _events(db, scan.id)


def test_transient_failures_retry_at_job_level(db, vault, settings):
    reg = ConnectorRegistry()
    reg.register(FlakyConnector)
    reg.enable("flaky", environment="test")
    FlakyConnector.fail_budget["n"] = 5  # exhausts run()'s 3 internal retries once

    user = _mk_user(db, with_aux=False)
    scan, _ = engine.start_scan(
        db, requester=user, settings=settings, registry=reg, vault=vault, inline=True
    )
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan.status == ScanStatus.DONE
    job = db.execute(select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)).scalar_one()
    assert job.status == JobStatus.DONE
    assert job.attempts == 2  # first attempt burned by transient failures, second succeeded


def test_scan_survives_worker_restart(db, registry, vault, settings):
    """M1-1 acceptance: kill the 'worker' mid-run; resume completes the scan."""
    user = _mk_user(db)
    scan = engine.create_scan(db, requester=user, settings=settings)
    assert engine.gate_scan(db, scan, settings).passed
    jobs = engine.dispatch_scan(db, scan, registry)
    assert len(jobs) == 2

    # Worker ran ONE job, then the process died.
    engine.run_connector_job(db, jobs[0].id, registry, vault)
    db.expire_all()
    assert db.get(Scan, scan.id).status == ScanStatus.RUNNING  # mid-flight

    # Simulate a job another dead worker left claimed-but-unfinished:
    j2 = db.get(ConnectorJob, jobs[1].id)
    j2.status = JobStatus.RUNNING
    j2.started_at = datetime.now(timezone.utc) - timedelta(seconds=9999)
    db.commit()

    # New worker boots → resume_stalled re-drives everything.
    summary = engine.resume_stalled(
        db, settings=settings, registry=registry, vault=vault
    )
    assert summary["requeued_jobs"] == 1
    assert summary["finalized_scans"] == 1
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan.status == ScanStatus.DONE
    findings = db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalars().all()
    assert len(findings) == 4


def test_job_rerun_is_idempotent(db, registry, vault, settings):
    """Re-running a connector's work must not duplicate findings (upsert on
    (scan_id, dedupe_key)) — this is what makes resume safe."""
    user = _mk_user(db)
    scan = engine.create_scan(db, requester=user, settings=settings)
    engine.gate_scan(db, scan, settings)
    jobs = engine.dispatch_scan(db, scan, registry)

    engine.run_connector_job(db, jobs[0].id, registry, vault)
    n1 = len(db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalars().all())

    # crash-after-persist-before-ack: job re-queued and re-run
    j = db.get(ConnectorJob, jobs[0].id)
    j.status = JobStatus.QUEUED
    db.commit()
    engine.run_connector_job(db, jobs[0].id, registry, vault)
    n2 = len(db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalars().all())
    assert n1 == n2  # no duplicates


def test_celery_task_wrappers_in_eager_mode(db, registry, vault, settings, monkeypatch):
    """The Celery layer is thin; prove task→engine wiring with eager mode."""
    from ayin.orchestrator import tasks as t
    from ayin.orchestrator.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    monkeypatch.setattr("ayin.orchestrator.tasks.global_registry", registry)
    monkeypatch.setattr(t, "_vault", lambda: vault)

    user = _mk_user(db)
    scan = engine.create_scan(db, requester=user, settings=settings)
    outcome = t.gate_and_dispatch.apply(args=[str(scan.id)]).get()
    assert outcome.startswith("dispatched:")
    db.expire_all()
    scan = db.get(Scan, scan.id)
    assert scan.status == ScanStatus.DONE  # eager mode ran jobs + finalize inline
