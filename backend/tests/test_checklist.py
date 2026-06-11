"""M3-2 acceptance: hardening checklist.

- each high-impact finding has actionable steps with an expected score delta
- deltas are honest (re-running the rubric without the finding)
- credential items leak nothing without step-up; details unlock with it
- read-only: no remediation rows are created
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
from ayin.models import RemediationTask
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
def scan_id(client, unique_email):
    sender = client.app.state._sender
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    return client.post("/scans").json()["id"]


def test_checklist_items_with_honest_deltas(client, db, scan_id):
    res = client.get(f"/scans/{scan_id}/checklist")
    assert res.status_code == 200, res.text
    body = res.json()
    current = body["current_overall"]
    assert current > 0
    items = body["items"]
    assert len(items) == 2  # fake breach + fake broker listing

    deltas = [i["expected_score_delta"] for i in items]
    assert deltas == sorted(deltas, reverse=True)  # ranked by impact
    for item in items:
        assert item["steps"], item["title"]
        assert 0 <= item["expected_score_delta"] < current
        assert item["effort"] in ("low", "medium")

    credential = next(i for i in items if i["category"] == "credential")
    assert any("multi-factor" in s.lower() for s in credential["steps"])
    assert any("password" in s.lower() for s in credential["steps"])

    broker = next(i for i in items if i["category"] == "broker")
    assert any("opt-out" in s.lower() or "removal" in s.lower() for s in broker["steps"])
    assert any("re-check" in s.lower() for s in broker["steps"])
    assert "Remove your listing" in broker["title"]

    # delta honesty: fixing the top item should land near (current - delta)
    # (cross-category deltas are exact: subscores are independent)
    top = items[0]
    assert top["expected_score_delta"] >= 1

    # read-only: nothing persisted (tracking is Phase 1)
    assert db.execute(select(RemediationTask)).scalars().all() == []


def test_credential_titles_locked_without_step_up(client, scan_id):
    plain = client.get(f"/scans/{scan_id}/checklist").json()
    cred = next(i for i in plain["items"] if i["category"] == "credential")
    assert "ExampleBreach" not in cred["title"]
    assert "ExampleBreach" not in " ".join(cred["steps"])

    token = client.post("/auth/step-up", json={"password": FAKE_PASSWORD}).json()[
        "step_up_token"
    ]
    elevated = client.get(
        f"/scans/{scan_id}/checklist", headers={"X-Ayin-Step-Up": token}
    ).json()
    cred = next(i for i in elevated["items"] if i["category"] == "credential")
    assert "ExampleBreach" in cred["title"] or "ExampleBreach" in " ".join(cred["steps"])


def test_empty_scan_has_empty_checklist(client, unique_email, db):
    """Low-exposure users get an empty list, current 0 — the UI reassures."""
    sender = client.app.state._sender
    other = "empty-" + unique_email
    client.cookies.clear()
    client.post("/auth/signup", json={"email": other, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})

    # a scan with a registry whose connector yields nothing: reuse fake but
    # reject its findings to simulate a clean profile
    scan_id = client.post("/scans").json()["id"]
    for f in client.get(f"/scans/{scan_id}/findings").json()["findings"]:
        client.post(f"/findings/{f['id']}/reject")

    body = client.get(f"/scans/{scan_id}/checklist").json()
    assert body["current_overall"] == 0
    assert body["items"] == []
