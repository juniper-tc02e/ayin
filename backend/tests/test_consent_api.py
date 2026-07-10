"""Consent endpoints (T1) — the subject-driven HTTP flow + the scan endpoint's
refusal to scan a third party without a live grant.

The requester is authenticated; the subject acts unauthenticated through the
emailed link (possession proves email control). We read the link token out of
the recorded email body, exactly as a subject would from their inbox.
"""

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.consent import _public_limiter
from ayin.config import get_settings
from ayin.models import Scan, Subject, User
from sqlalchemy import select
from tests.test_auth import FAKE_PASSWORD, RecordingSender


@pytest.fixture()
def sender():
    return RecordingSender()


def _t1_enabled_settings():
    # T1 is flag-gated and OFF by default; enable it for the endpoint tests.
    return get_settings().model_copy(update={"consent_t1_enabled": True})


@pytest.fixture()
def client(sender):
    _public_limiter.reset()  # process-global throttle — start each test fresh
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: sender
    app.dependency_overrides[get_settings] = _t1_enabled_settings
    with TestClient(app) as c:
        yield c


def test_t1_surface_hidden_when_flag_off(sender):
    # Default settings (flag off): the whole /consent surface 404s and /config
    # advertises it as disabled.
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: sender
    with TestClient(app) as c:
        assert c.get("/config").json()["consent_t1_enabled"] is False
        _signup(c, f"req-{uuid.uuid4().hex[:8]}@example.org")
        r = c.post("/consent/requests", json={"subject_email": "x@example.org", "purpose": "p"})
        assert r.status_code == 404
        assert c.get("/consent/grants").status_code == 404


def _signup(client, email):
    assert client.post(
        "/auth/signup", json={"email": email, "password": FAKE_PASSWORD}
    ).status_code == 201


def _accept_tos(client):
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})


def _token_from_email(sender) -> str:
    body = sender.sent[-1]["body"]
    m = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert m, f"no consent token in email body: {body!r}"
    return m.group(1)


def test_full_consent_endpoint_flow(client, sender):
    req_email = f"req-{uuid.uuid4().hex[:8]}@example.org"
    subj_email = f"subj-{uuid.uuid4().hex[:8]}@example.org"
    _signup(client, req_email)

    # Requester asks.
    r = client.post("/consent/requests", json={
        "subject_email": subj_email, "usernames": ["Zoe_X"], "purpose": "exec protection",
    })
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    assert sender.sent[-1]["to"] == subj_email  # delivered to the SUBJECT
    token = _token_from_email(sender)

    # Subject opens the link (unauthenticated).
    client.cookies.clear()
    ask = client.get(f"/consent/requests/{token}")
    assert ask.status_code == 200
    assert ask.json()["requester_email"] == req_email
    assert ask.json()["purpose"] == "exec protection"
    assert ask.json()["usernames"] == ["Zoe_X"]

    # No minors: must attest adulthood.
    bad = client.post(f"/consent/requests/{token}/accept", json={"adult_attested": False})
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "adult_attestation_required"

    # Subject authorizes.
    ok = client.post(f"/consent/requests/{token}/accept", json={"adult_attested": True})
    assert ok.status_code == 200
    grant_subject_id = ok.json()["subject_id"]
    assert ok.json()["granted"] is True

    # Link is single-use.
    assert client.get(f"/consent/requests/{token}").status_code == 404

    # Requester sees the live grant, then revokes it.
    client.cookies.clear()
    res = client.post("/auth/login", json={"email": req_email, "password": FAKE_PASSWORD})
    assert res.status_code == 200
    grants = client.get("/consent/grants").json()
    assert len(grants) == 1
    assert grants[0]["subject_id"] == grant_subject_id
    assert grants[0]["subject_email"] == subj_email
    grant_id = grants[0]["id"]

    assert client.post(f"/consent/grants/{grant_id}/revoke").status_code == 204
    assert client.get("/consent/grants").json() == []


def test_cannot_request_your_own_email(client):
    req_email = f"req-{uuid.uuid4().hex[:8]}@example.org"
    _signup(client, req_email)
    r = client.post("/consent/requests", json={
        "subject_email": req_email, "usernames": [], "purpose": "x",
    })
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "cannot_request_self"


def test_declined_ask_cannot_be_accepted(client, sender):
    _signup(client, f"req-{uuid.uuid4().hex[:8]}@example.org")
    client.post("/consent/requests", json={
        "subject_email": f"subj-{uuid.uuid4().hex[:8]}@example.org",
        "usernames": [], "purpose": "x",
    })
    token = _token_from_email(sender)
    client.cookies.clear()
    assert client.post(f"/consent/requests/{token}/decline").status_code == 204
    accept = client.post(f"/consent/requests/{token}/accept", json={"adult_attested": True})
    assert accept.status_code == 404


def test_scan_endpoint_refuses_third_party_without_consent(client, db):
    # A requester who has done nothing to earn consent cannot scan a stranger.
    _signup(client, f"req-{uuid.uuid4().hex[:8]}@example.org")
    _accept_tos(client)

    stranger = User(email=f"stranger-{uuid.uuid4().hex[:8]}@example.org", password_hash="x")
    db.add(stranger)
    db.flush()
    stranger_subject = Subject(owner_user_id=stranger.id)
    db.add(stranger_subject)
    db.flush()
    db.commit()

    r = client.post("/scans", json={"subject_id": str(stranger_subject.id)})
    assert r.status_code == 403
    assert r.json()["detail"]["reason"].startswith("no_consent")


def test_self_scan_still_works_with_no_body(client):
    # The default (no body) path is unchanged: you scan yourself.
    _signup(client, f"req-{uuid.uuid4().hex[:8]}@example.org")
    _accept_tos(client)
    r = client.post("/scans")
    # Either accepted, or refused for a NON-consent reason (e.g. no verified
    # anchor) — never the consent refusal, since it's a self-scan.
    if r.status_code >= 400:
        assert not r.json()["detail"]["reason"].startswith("no_consent")


def test_accept_emails_a_revoke_link_that_works_unauthenticated(client, sender):
    # #1: accepting emails the SUBJECT a one-click revoke link that withdraws
    # consent with no account.
    req_email = f"req-{uuid.uuid4().hex[:8]}@example.org"
    subj_email = f"subj-{uuid.uuid4().hex[:8]}@example.org"
    _signup(client, req_email)
    client.post("/consent/requests", json={
        "subject_email": subj_email, "usernames": [], "purpose": "x",
    })
    ask_token = _token_from_email(sender)  # the ask email is the latest so far

    client.cookies.clear()
    assert client.post(
        f"/consent/requests/{ask_token}/accept", json={"adult_attested": True}
    ).status_code == 200

    # The newest email is now the confirmation, to the subject, with a revoke link.
    conf = sender.sent[-1]
    assert conf["to"] == subj_email
    m = re.search(r"/consent/revoke\?token=([A-Za-z0-9_\-]+)", conf["body"])
    assert m, conf["body"]
    revoke_token = m.group(1)

    # One-click revoke, unauthenticated, works.
    assert client.post(f"/consent/revoke/{revoke_token}").status_code == 204
    # And a bogus revoke token 404s.
    assert client.post("/consent/revoke/not-a-real-token").status_code == 404

    # The requester now holds no live grants.
    client.cookies.clear()
    client.post("/auth/login", json={"email": req_email, "password": FAKE_PASSWORD})
    assert client.get("/consent/grants").json() == []


def test_requester_cannot_read_a_consented_subjects_scan(client, db):
    # #5 result-delivery: a third party's scan belongs to the SUBJECT. Even the
    # requester who ran it can't read its findings/report (owner-scoped).
    req_email = f"req-{uuid.uuid4().hex[:8]}@example.org"
    _signup(client, req_email)
    me = db.execute(select(User).where(User.email == req_email)).scalar_one()
    stranger = User(email=f"s-{uuid.uuid4().hex[:8]}@example.org", password_hash="x")
    db.add(stranger)
    db.flush()
    stranger_subject = Subject(owner_user_id=stranger.id)
    db.add(stranger_subject)
    db.flush()
    scan = Scan(requester_user_id=me.id, subject_id=stranger_subject.id)
    db.add(scan)
    db.flush()
    db.commit()

    assert client.get(f"/scans/{scan.id}").status_code == 404
    assert client.get(f"/scans/{scan.id}/findings").status_code == 404


def test_public_token_endpoints_are_ip_throttled(client):
    # #6: the unauthenticated token surface is per-IP rate limited (30 / window).
    bogus = "z" * 44
    for _ in range(30):
        client.get(f"/consent/requests/{bogus}")  # 404 (unknown token) but counts
    assert client.get(f"/consent/requests/{bogus}").status_code == 429
