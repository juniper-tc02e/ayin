"""M3-3 acceptance: abuse refusal + safety hold.

- a scan tripping a heuristic is refused/held with a logged reason
- victim-protection matches are NEVER revealed to the requester
- a false-positive appeal path exists and opens a review case

All identifiers clearly fake.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AbuseSignal, AuditRecord, User
from ayin.models.enums import (
    AbuseSignalKind,
    AbuseSignalSeverity,
    IdentifierKind,
)
from ayin.models.protection import ProtectionEntry
from ayin.safety.hashing import identifier_hash
from ayin.vault import NullVault
from tests.test_auth import FAKE_PASSWORD, RecordingSender

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def client():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: RecordingSender()
    app.dependency_overrides[get_registry] = lambda: reg
    app.dependency_overrides[get_vault] = lambda: NullVault()
    with TestClient(app) as c:
        yield c


def _ready_user(client, email):
    sender = RecordingSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    client.post("/auth/signup", json={"email": email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})


def test_k12_email_seed_refused_as_minor(client, db):
    _ready_user(client, f"student-{uuid.uuid4().hex[:6]}@lincoln.k12.ca.us")
    res = client.post("/scans")
    assert res.status_code == 409  # refusal (non-rate-limit) maps to conflict
    reason = res.json()["detail"]["reason"]
    assert reason.startswith("minor_subject")
    assert "appeal" in reason.lower()  # the user is told how to contest it

    signals = db.execute(select(AbuseSignal)).scalars().all()
    assert any(s.kind == AbuseSignalKind.MINOR_SUBJECT for s in signals)
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "scan.refused" in events


def test_birthyear_username_refused_as_minor(client, db, unique_email):
    _ready_user(client, unique_email)
    client.post("/identifiers", json={"kind": "username", "value": "fake_kid_2012"})
    res = client.post("/scans")
    assert res.status_code == 409
    assert res.json()["detail"]["reason"].startswith("minor_subject")


def test_old_birthyear_not_a_minor_signal(client, unique_email):
    _ready_user(client, unique_email)
    client.post("/identifiers", json={"kind": "username", "value": "fake_adult_1990"})
    assert client.post("/scans").status_code == 202  # 1990 is fine


def test_protection_match_holds_without_revealing_why(client, db, unique_email):
    _ready_user(client, unique_email)
    # a protected person's name is on the staff-curated list (hash only)
    db.add(ProtectionEntry(
        kind="full_name",
        value_hash=identifier_hash(IdentifierKind.FULL_NAME, "protected fake person"),
        note="fixture case #123",
    ))
    db.commit()
    client.post("/identifiers", json={"kind": "full_name", "value": "Protected Fake Person"})

    res = client.post("/scans")
    assert res.status_code == 202  # held, not refused — returns the scan
    body = res.json()
    assert body["status"] == "held"
    # the requester must never learn it was a protection-list match
    assert "victim" not in (body["error"] or "").lower()
    assert "protect" not in (body["error"] or "").lower()
    assert "manual_review" in body["error"]

    signals = db.execute(select(AbuseSignal)).scalars().all()
    assert any(s.kind == AbuseSignalKind.VICTIM_PROTECTION for s in signals)
    held_events = db.execute(
        select(AuditRecord).where(AuditRecord.event_type == "scan.held")
    ).scalars().all()
    assert held_events  # reason logged for reviewers


def test_block_severity_signal_refuses(client, db, unique_email):
    _ready_user(client, unique_email)
    user = db.execute(select(User)).scalars().first()
    db.add(AbuseSignal(user_id=user.id, kind=AbuseSignalKind.ANOMALY,
                       severity=AbuseSignalSeverity.BLOCK, detail={}))
    db.commit()
    res = client.post("/scans")
    assert res.status_code == 409
    assert "account_flagged" in res.json()["detail"]["reason"]


def test_appeal_path_opens_review_case(client, db):
    _ready_user(client, f"student-{uuid.uuid4().hex[:6]}@x.k12.ny.us")
    refused = client.post("/scans")
    scan_id = refused.json()["detail"]["scan_id"]

    res = client.post(
        f"/scans/{scan_id}/appeal",
        json={"message": "This is my old school alumni address — I'm 28."},
    )
    assert res.status_code == 200

    appeal = db.execute(
        select(AbuseSignal).where(AbuseSignal.kind == AbuseSignalKind.APPEAL)
    ).scalar_one()
    assert appeal.detail["message"].startswith("This is my old school")
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "scan.appeal_submitted" in events

    dup = client.post(f"/scans/{scan_id}/appeal", json={"message": "appealing again!!"})
    assert dup.status_code == 409


def test_appeal_only_for_refused_or_held(client, unique_email):
    _ready_user(client, unique_email)
    scan_id = client.post("/scans").json()["id"]  # completes fine
    res = client.post(f"/scans/{scan_id}/appeal", json={"message": "nothing to appeal here"})
    assert res.status_code == 409


def test_normal_scan_unaffected_by_heuristics(client, unique_email):
    _ready_user(client, unique_email)
    assert client.post("/scans").status_code == 202
