"""M0-3 acceptance: signup / login / logout; isolation; audit on auth events.

All credentials here are clearly fake test values.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.config import get_settings
from ayin.models import AuditRecord, Subject, User

FAKE_PASSWORD = "correct-horse-battery-fake"


class RecordingSender:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})

    def last_link_token(self) -> str:
        body = self.sent[-1]["body"]
        for line in body.splitlines():
            if "token=" in line:
                return line.strip().split("token=")[1]
        raise AssertionError("no verification link in last email")


@pytest.fixture()
def sender():
    return RecordingSender()


@pytest.fixture()
def client(sender):
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: sender
    with TestClient(app) as c:
        yield c


def _signup(client, email, password=FAKE_PASSWORD):
    return client.post("/auth/signup", json={"email": email, "password": password})


def test_signup_creates_user_subject_and_audits(client, db, unique_email):
    res = _signup(client, unique_email)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == unique_email
    assert body["email_verified"] is False
    assert "ayin_session" in res.cookies

    user = db.execute(select(User).where(User.email == unique_email)).scalar_one()
    assert user.password_hash != FAKE_PASSWORD  # hashed, never plaintext
    assert user.password_hash.startswith("$argon2")
    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one()
    assert subject.exclusion_state == "none"
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "auth.signup" in events


def test_signup_sends_verification_email(client, sender, unique_email):
    _signup(client, unique_email)
    assert len(sender.sent) == 1
    assert sender.sent[0]["to"] == unique_email
    assert "verify-email?token=" in sender.sent[0]["body"]


def test_duplicate_email_conflicts(client, unique_email):
    assert _signup(client, unique_email).status_code == 201
    assert _signup(client, unique_email).status_code == 409


def test_weak_password_rejected(client, unique_email):
    res = _signup(client, unique_email, password="short")
    assert res.status_code == 422


def test_login_logout_me_roundtrip(client, db, unique_email):
    _signup(client, unique_email)
    client.cookies.clear()

    bad = client.post("/auth/login", json={"email": unique_email, "password": "wrong-pass-x"})
    assert bad.status_code == 401

    ok = client.post("/auth/login", json={"email": unique_email, "password": FAKE_PASSWORD})
    assert ok.status_code == 200

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == unique_email

    client.post("/auth/logout")
    client.cookies.clear()
    assert client.get("/auth/me").status_code == 401

    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "auth.login_failed" in events
    assert "auth.login" in events


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_email_verification_flow_is_single_use(client, sender, db, unique_email):
    _signup(client, unique_email)
    token = sender.last_link_token()

    res = client.post("/auth/verify-email", json={"token": token})
    assert res.status_code == 200
    assert res.json()["email_verified"] is True

    again = client.post("/auth/verify-email", json={"token": token})
    assert again.status_code == 400  # single-use

    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "auth.email_verified" in events


def test_garbage_verification_token_rejected(client):
    res = client.post("/auth/verify-email", json={"token": "x" * 43})
    assert res.status_code == 400


def test_step_up_requires_correct_password(client, unique_email):
    _signup(client, unique_email)
    bad = client.post("/auth/step-up", json={"password": "not-it-at-all"})
    assert bad.status_code == 401
    ok = client.post("/auth/step-up", json={"password": FAKE_PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["step_up_token"]


def test_sessions_are_per_user(client, unique_email):
    """A's cookie must never resolve to B (per-user isolation)."""
    _signup(client, unique_email)
    a_cookie = client.cookies.get("ayin_session")

    b_email = "other-" + unique_email
    client.cookies.clear()
    _signup(client, b_email)

    client.cookies.clear()
    client.cookies.set("ayin_session", a_cookie)
    assert client.get("/auth/me").json()["email"] == unique_email
