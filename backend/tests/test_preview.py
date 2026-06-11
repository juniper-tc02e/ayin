"""M4-1 acceptance (backend half): pre-scan transparency.

- "here's what we'll check and why" + ETA before scanning
- seeds annotated honestly: verified / auxiliary / unverified / excluded
- blockers guide the non-technical user to readiness
"""

import pytest
from fastapi.testclient import TestClient

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
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


def test_preview_guides_unready_user_to_readiness(client, unique_email):
    sender = client.app.state._sender
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})

    res = client.get("/scans/preview")
    assert res.status_code == 200
    body = res.json()
    assert body["ready"] is False
    assert any("Verify control" in b for b in body["blockers"])
    assert any("terms" in b for b in body["blockers"])
    seed = body["seeds"][0]
    assert seed["will_scan"] is False
    assert "verify" in seed["reason"].lower()

    # verify + accept → ready, with what/why/eta
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})

    body = client.get("/scans/preview").json()
    assert body["ready"] is True
    assert body["blockers"] == []
    assert body["seeds"][0]["will_scan"] is True
    assert "verified" in body["seeds"][0]["reason"]
    assert len(body["connectors"]) == 1
    c = body["connectors"][0]
    assert c["why"] and c["categories"] and c["eta_seconds"] > 0
    assert body["eta_seconds"] >= c["eta_seconds"]


def test_preview_annotates_auxiliary_seeds(client, unique_email):
    sender = client.app.state._sender
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    client.post("/identifiers", json={"kind": "username", "value": "fake_preview_handle"})

    body = client.get("/scans/preview").json()
    by_kind = {s["kind"]: s for s in body["seeds"]}
    assert by_kind["username"]["will_scan"] is True
    assert "auxiliary" in by_kind["username"]["reason"]
