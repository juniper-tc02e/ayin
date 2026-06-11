"""M4-2 acceptance: analytics instrumentation.

- each §13.7 metric is queryable (funnel_report)
- NO PII leaves the app in analytics payloads — the screen rejects emails,
  phone-like digit runs, free text, unknown keys, unknown events
- the full product flow emits the funnel events end-to-end
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.analytics import track
from ayin.analytics.events import AnalyticsPIIError, user_ref_for
from ayin.analytics.funnel import format_report, funnel_report
from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AnalyticsEvent
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


# ── the PII screen ───────────────────────────────────────────────────


def test_screen_rejects_emails_in_values(db):
    with pytest.raises(AnalyticsPIIError):
        track(db, "scan_started", properties={"kind": "leak@example.org"})


def test_screen_rejects_phone_like_digit_runs(db):
    with pytest.raises(AnalyticsPIIError):
        track(db, "scan_started", properties={"kind": "15551234567"})


def test_screen_rejects_unknown_property_keys(db):
    with pytest.raises(AnalyticsPIIError):
        track(db, "scan_started", properties={"email": "x"})
    with pytest.raises(AnalyticsPIIError):
        track(db, "scan_started", properties={"summary": "short"})


def test_screen_rejects_long_free_text_and_dicts(db):
    with pytest.raises(AnalyticsPIIError):
        track(db, "scan_started", properties={"kind": "x" * 65})
    with pytest.raises(AnalyticsPIIError):
        track(db, "scan_started", properties={"kind": {"nested": "object"}})


def test_unknown_event_names_rejected(db):
    with pytest.raises(AnalyticsPIIError):
        track(db, "totally_new_event")


def test_user_ref_is_pseudonymous(db):
    uid = uuid.uuid4()
    track(db, "scan_started", user_id=uid)
    db.commit()
    row = db.execute(select(AnalyticsEvent)).scalar_one()
    assert row.user_ref == user_ref_for(uid)
    assert str(uid) not in row.user_ref  # not the raw id
    assert len(row.user_ref) == 16


# ── funnel end-to-end ────────────────────────────────────────────────


def _full_journey(client, email):
    sender = client.app.state._sender
    client.post("/auth/signup", json={"email": email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    scan_id = client.post("/scans").json()["id"]
    client.post("/analytics/events", json={"name": "report_viewed", "scan_id": scan_id})
    return scan_id


def test_product_flow_emits_funnel_events(client, db, unique_email):
    scan_id = _full_journey(client, unique_email)
    # one action: review a finding
    page = client.get(f"/scans/{scan_id}/findings").json()
    fid = page["findings"][0]["id"]
    client.post(f"/findings/{fid}/confirm") if page["findings"][0][
        "match_status"
    ] == "possible" else client.post(
        "/analytics/events",
        json={"name": "action_started", "scan_id": scan_id, "properties": {"category": "credential"}},
    )

    names = set(db.execute(select(AnalyticsEvent.name)).scalars())
    for expected in ["signup_completed", "identifier_added", "identifier_verified",
                     "tos_accepted", "scan_started", "scan_completed", "report_viewed"]:
        assert expected in names, expected

    report = funnel_report(db)
    assert report.users_started == 1
    assert report.users_completed == 1
    assert report.users_activated == 1
    assert report.completion_rate == 1.0
    assert report.users_acted == 1
    assert "completion 100%" in format_report(report)


def test_no_pii_anywhere_in_stored_events(client, db, unique_email):
    _full_journey(client, unique_email)
    rows = db.execute(select(AnalyticsEvent)).scalars().all()
    blob = " ".join(f"{r.name} {r.user_ref} {r.properties}" for r in rows)
    assert unique_email not in blob
    assert "@" not in blob


def test_client_event_restrictions(client, db, unique_email):
    scan_id = _full_journey(client, unique_email)
    # unknown client event
    res = client.post("/analytics/events", json={"name": "scan_completed"})
    assert res.status_code == 422
    # foreign scan
    res = client.post(
        "/analytics/events",
        json={"name": "report_viewed", "scan_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404
    # PII smuggling via client properties
    res = client.post(
        "/analytics/events",
        json={"name": "action_started", "scan_id": scan_id,
              "properties": {"category": "x@example.org"}},
    )
    assert res.status_code == 422


def test_refusal_reason_codes_tracked_without_detail(client, db):
    sender = client.app.state._sender
    email = f"student-{uuid.uuid4().hex[:6]}@x.k12.tx.us"
    client.post("/auth/signup", json={"email": email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    client.post("/scans")
    refused = db.execute(
        select(AnalyticsEvent).where(AnalyticsEvent.name == "scan_refused")
    ).scalar_one()
    assert refused.properties["reason_code"] == "minor_subject"
    assert "k12" not in str(refused.properties)  # no identifier detail leaks
