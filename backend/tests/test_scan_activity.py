"""E1 API acceptance: GET /scans/{scan_id}/activity — the audit-trail surface.

- serves the pipeline trail (created → gated → started → connector →
  resolved → scored → completed) in chain order, from real AuditRecords
- double allowlist holds: unlisted event types never appear; unlisted detail
  fields are stripped even on listed events (proven against raw rows that
  DO carry them — cost_usd, exception text, injected extras)
- per-user isolation (404, never 403)
- reading the trail writes its own data.access audit record
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord, Scan
from ayin.safety.audit import record_scan_event, system_actor
from ayin.vault import NullVault
from tests.test_auth import FAKE_PASSWORD, RecordingSender


@pytest.fixture()
def sender():
    return RecordingSender()


@pytest.fixture()
def registry():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    return reg


@pytest.fixture()
def client(sender, registry):
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: sender
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_vault] = lambda: NullVault()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ready_user(client, sender, unique_email):
    """Signed up, email verified, ToS accepted — allowed to scan."""
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    token = sender.last_link_token()
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    version = client.get("/tos").json()["current_version"]
    assert client.post("/tos/accept", json={"version": version}).status_code == 200
    return unique_email


def test_activity_serves_the_pipeline_trail_in_order(client, ready_user):
    scan_id = client.post("/scans").json()["id"]

    res = client.get(f"/scans/{scan_id}/activity")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["scan_id"] == scan_id

    ids = [e["id"] for e in body["events"]]
    assert ids == sorted(ids)  # audit-chain order, oldest first

    types = [e["event_type"] for e in body["events"]]
    for expected in (
        "scan.created", "scan.gated", "scan.started", "scan.connector_finished",
        "scan.resolved", "scan.scored", "scan.completed",
    ):
        assert expected in types, f"missing {expected} in {types}"

    by_type = {e["event_type"]: e for e in body["events"]}
    assert by_type["scan.created"]["actor"] == "user"
    assert by_type["scan.started"]["actor"] == "system:orchestrator"
    assert by_type["scan.started"]["detail"]["connectors"] == ["fake"]
    assert by_type["scan.scored"]["detail"]["overall"] >= 0
    assert by_type["scan.connector_finished"]["detail"]["connector"] == "fake"


def test_internal_telemetry_never_leaves_the_audit_table(client, db, ready_user):
    scan_id = client.post("/scans").json()["id"]

    # the raw row really does carry cost telemetry — redaction, not absence
    raw = db.execute(
        select(AuditRecord).where(
            AuditRecord.scan_id == uuid.UUID(scan_id),
            AuditRecord.event_type == "scan.connector_finished",
        )
    ).scalars().first()
    assert raw is not None and "cost_usd" in raw.detail

    body = client.get(f"/scans/{scan_id}/activity").json()
    flat = str(body)
    assert "cost_usd" not in flat
    assert "prev_hash" not in flat
    finished = next(
        e for e in body["events"] if e["event_type"] == "scan.connector_finished"
    )
    assert finished["detail"]["findings"] == 2  # allowlisted fields survive


def test_planner_detail_allowlist_strips_unlisted_fields(client, db, ready_user):
    """Planner events carry the model's reasoning (serve it) — but anything
    outside the per-event allowlist is stripped, and planner_fallback's
    exception text (which can embed internal endpoints) never surfaces."""
    scan_id = client.post("/scans").json()["id"]
    scan = db.get(Scan, uuid.UUID(scan_id))
    record_scan_event(
        db, actor=system_actor("planner"), event_type="scan.planner_decision",
        scan_id=scan.id, subject_id=scan.subject_id,
        detail={"connector": "fake", "seed_ref": "all", "step": 1,
                "reasoning": "breach exposure first — highest exploitability",
                "model": "qwen-test", "internal_debug": "NEVER-SHOWN"},
    )
    record_scan_event(
        db, actor=system_actor("planner"), event_type="scan.planner_fallback",
        scan_id=scan.id, subject_id=scan.subject_id,
        detail={"reason": "LLMUnavailable: http://internal-host:11434 unreachable"},
    )
    db.commit()

    body = client.get(f"/scans/{scan_id}/activity").json()
    by_type = {e["event_type"]: e for e in body["events"]}

    decision = by_type["scan.planner_decision"]
    assert decision["actor"] == "system:planner"
    assert decision["detail"]["reasoning"].startswith("breach exposure first")
    assert decision["detail"]["connector"] == "fake"
    assert "internal_debug" not in decision["detail"]

    assert by_type["scan.planner_fallback"]["detail"] == {}
    assert "internal-host" not in str(body)


def test_unlisted_event_types_never_appear(client, db, ready_user):
    scan_id = client.post("/scans").json()["id"]
    # generate data.access rows scoped to this scan
    client.get(f"/scans/{scan_id}/findings")
    client.get(f"/scans/{scan_id}/score")
    assert db.execute(
        select(AuditRecord).where(
            AuditRecord.scan_id == uuid.UUID(scan_id),
            AuditRecord.event_type == "data.access",
        )
    ).scalars().first() is not None

    types = {
        e["event_type"]
        for e in client.get(f"/scans/{scan_id}/activity").json()["events"]
    }
    assert "data.access" not in types


def test_activity_isolated_between_users(client, sender, ready_user, unique_email):
    scan_id = client.post("/scans").json()["id"]

    client.cookies.clear()
    other = "other-" + unique_email
    client.post("/auth/signup", json={"email": other, "password": FAKE_PASSWORD})
    assert client.get(f"/scans/{scan_id}/activity").status_code == 404


def test_activity_read_is_itself_audited(client, db, ready_user):
    scan_id = client.post("/scans").json()["id"]
    assert client.get(f"/scans/{scan_id}/activity").status_code == 200

    rec = db.execute(
        select(AuditRecord)
        .where(
            AuditRecord.event_type == "data.access",
            AuditRecord.resource == "activity",
        )
        .order_by(AuditRecord.id.desc())
    ).scalars().first()
    assert rec is not None
    assert str(rec.scan_id) == scan_id
    assert rec.purpose == "self-view"
