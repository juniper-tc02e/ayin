"""M0-5 acceptance: versioned ToS/AUP gate.

- scanning (anything behind require_tos) is blocked until the acceptance
  row exists for the CURRENT version
- a version bump re-prompts (old acceptance no longer satisfies the gate)
"""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.config import Settings, get_settings
from ayin.models import AuditRecord, TosAcceptance
from ayin.safety.tos import TOS_REQUIRED_CODE, require_tos
from tests.test_auth import FAKE_PASSWORD, RecordingSender


def _build_client(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_email_sender] = lambda: RecordingSender()
    # Stand-in for the scan-start endpoint (M1-1) — same gate it will use.
    @app.post("/_test/gated-scan-start")
    def gated(user=Depends(require_tos)):  # noqa: ANN001
        return {"ok": True}
    # The test app must resolve the same Settings instance the gate sees.
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture()
def client():
    return _build_client(get_settings())


@pytest.fixture()
def signed_up(client, unique_email):
    res = client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    assert res.status_code == 201
    return res.json()


def test_fresh_user_has_not_accepted(client, signed_up):
    res = client.get("/tos")
    assert res.status_code == 200
    body = res.json()
    assert body["accepted_current"] is False
    assert body["current_version"]


def test_scan_start_blocked_until_accepted(client, db, signed_up):
    blocked = client.post("/_test/gated-scan-start")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == TOS_REQUIRED_CODE

    version = client.get("/tos").json()["current_version"]
    accepted = client.post("/tos/accept", json={"version": version})
    assert accepted.status_code == 200
    assert accepted.json()["accepted_current"] is True

    ok = client.post("/_test/gated-scan-start")
    assert ok.status_code == 200

    row = db.execute(select(TosAcceptance)).scalars().one()
    assert row.version == version
    assert row.accepted_at is not None
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "tos.accepted" in events


def test_accepting_stale_version_conflicts(client, signed_up):
    res = client.post("/tos/accept", json={"version": "1999-01-01"})
    assert res.status_code == 409


def test_re_accept_is_idempotent(client, db, signed_up):
    version = client.get("/tos").json()["current_version"]
    assert client.post("/tos/accept", json={"version": version}).status_code == 200
    assert client.post("/tos/accept", json={"version": version}).status_code == 200
    rows = db.execute(select(TosAcceptance)).scalars().all()
    assert len(rows) == 1


def test_version_bump_reprompts(unique_email):
    """Material ToS change → everyone re-accepts before scanning again."""
    v1 = get_settings().model_copy(update={"tos_current_version": "2026-06-10"})
    client = _build_client(v1)
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    client.post("/tos/accept", json={"version": "2026-06-10"})
    assert client.post("/_test/gated-scan-start").status_code == 200

    v2 = v1.model_copy(update={"tos_current_version": "2026-09-01"})
    client2 = _build_client(v2)
    login = client2.post(
        "/auth/login", json={"email": unique_email, "password": FAKE_PASSWORD}
    )
    assert login.status_code == 200

    status = client2.get("/tos").json()
    assert status["current_version"] == "2026-09-01"
    assert status["accepted_current"] is False  # old acceptance no longer counts

    blocked = client2.post("/_test/gated-scan-start")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == TOS_REQUIRED_CODE

    client2.post("/tos/accept", json={"version": "2026-09-01"})
    assert client2.post("/_test/gated-scan-start").status_code == 200
