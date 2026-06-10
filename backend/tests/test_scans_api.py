"""M1-1 API acceptance: the /scans surface.

- ToS gate blocks scan-start (the M0-5 dependency, now mounted for real)
- gate refusals map to clear HTTP codes
- inline execution completes the scan and serves findings
- credential findings are REDACTED until step-up; unlock is audited
- per-user isolation on scans + findings
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord
from ayin.safety.tos import TOS_REQUIRED_CODE
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


def test_scan_blocked_without_tos(client, sender, unique_email):
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    token = sender.last_link_token()
    client.post("/auth/verify-email", json={"token": token})
    res = client.post("/scans")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == TOS_REQUIRED_CODE


def test_scan_refused_without_verified_anchor(client, sender, unique_email):
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    res = client.post("/scans")  # email never verified
    assert res.status_code == 422
    assert "no_verified_anchor" in res.json()["detail"]["reason"]
    assert res.json()["detail"]["scan_id"]  # refusal is recorded, not vanished


def test_scan_completes_inline_and_lists(client, ready_user):
    res = client.post("/scans")
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "done"
    assert body["progress"]["jobs_total"] == 1
    assert body["progress"]["jobs_done"] == 1
    assert body["jobs"][0]["connector_id"] == "fake"
    assert body["jobs"][0]["findings_count"] == 2  # breach + broker for the email

    listing = client.get("/scans")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    detail = client.get(f"/scans/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "done"


def test_credential_findings_locked_until_step_up(client, db, ready_user):
    scan_id = client.post("/scans").json()["id"]

    page = client.get(f"/scans/{scan_id}/findings").json()
    assert page["locked_credential_findings"] == 1
    by_cat = {f["category"]: f for f in page["findings"]}
    cred = by_cat["credential"]
    assert cred["step_up_required"] is True
    assert cred["payload"] == {}
    assert "re-enter your password" in cred["summary"]
    assert "ExampleBreach" not in str(page)  # breach name must not leak when locked
    broker = by_cat["broker"]
    assert broker["step_up_required"] is False
    assert broker["payload"]["removable"] is True

    token = client.post("/auth/step-up", json={"password": FAKE_PASSWORD}).json()[
        "step_up_token"
    ]
    unlocked = client.get(
        f"/scans/{scan_id}/findings", headers={"X-Ayin-Step-Up": token}
    ).json()
    assert unlocked["locked_credential_findings"] == 0
    cred = next(f for f in unlocked["findings"] if f["category"] == "credential")
    assert cred["payload"]["breach_name"].startswith("ExampleBreach")
    assert cred["step_up_required"] is False

    resources = db.execute(
        select(AuditRecord.resource).where(AuditRecord.event_type == "data.access")
    ).scalars().all()
    assert "findings" in resources
    assert "findings.credential" in resources  # the unlock itself is audited


def test_burst_rate_limit_blocks_with_clear_message(client, ready_user):
    assert client.post("/scans").status_code == 202
    assert client.post("/scans").status_code == 202  # burst default = 2
    res = client.post("/scans")
    assert res.status_code == 429
    assert "Too many scans" in res.json()["detail"]["reason"]


def test_scans_are_isolated_between_users(client, sender, ready_user, unique_email):
    scan_id = client.post("/scans").json()["id"]

    client.cookies.clear()
    other = "other-" + unique_email
    client.post("/auth/signup", json={"email": other, "password": FAKE_PASSWORD})
    assert client.get(f"/scans/{scan_id}").status_code == 404
    assert client.get(f"/scans/{scan_id}/findings").status_code == 404
    assert client.get("/scans").json() == []
