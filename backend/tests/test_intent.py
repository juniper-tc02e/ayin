"""M4-4 acceptance: monitoring/removal intent capture.

- intent captured per user, idempotent, audited
- reportable as a % of activated users (funnel)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.analytics.funnel import funnel_report
from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord
from ayin.models.intent import IntentSignal
from ayin.vault import NullVault
from tests.test_auth import FAKE_PASSWORD, RecordingSender


@pytest.fixture()
def client():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    app = create_app(get_settings())
    sender = RecordingSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    app.dependency_overrides[get_registry] = lambda: reg
    app.dependency_overrides[get_vault] = lambda: NullVault()
    app.state._sender = sender
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def activated_user(client, unique_email):
    """Signed up, scanned, viewed report — an 'activated' user per §13.7."""
    sender = client.app.state._sender
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    scan_id = client.post("/scans").json()["id"]
    client.post("/analytics/events", json={"name": "report_viewed", "scan_id": scan_id})
    return scan_id


def test_intent_capture_idempotent_and_audited(client, db, activated_user):
    assert client.get("/intent").json() == {"monitoring": False, "removal": False}

    res = client.post("/intent", json={"kind": "monitoring", "scan_id": activated_user})
    assert res.status_code == 200
    assert res.json()["monitoring"] is True

    client.post("/intent", json={"kind": "monitoring"})  # again — no dup
    rows = db.execute(select(IntentSignal)).scalars().all()
    assert len(rows) == 1

    client.post("/intent", json={"kind": "removal"})
    assert client.get("/intent").json() == {"monitoring": True, "removal": True}

    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert events.count("intent.captured") == 2


def test_intent_reportable_as_percent_of_activated(client, db, activated_user):
    client.post("/intent", json={"kind": "monitoring", "scan_id": activated_user})
    report = funnel_report(db)
    assert report.users_activated == 1
    assert report.users_intent == 1
    assert report.intent_rate == 1.0  # 100% of activated users raised a hand
