"""M0-4 acceptance: identifier verification + the sensitive-results gate.

- unverified identifier cannot surface sensitive results (visibility filter)
- verification state stored on the Identifier
- email link + phone OTP flows; OTP attempt cap
- per-user isolation (404 on foreign identifiers)
- seed removal cascades its findings (data minimization)

All values clearly fake.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.identifiers import get_sms_sender
from ayin.config import get_settings
from ayin.models import AuditRecord, Finding, Identifier, Scan, Subject, User
from ayin.models.enums import FindingCategory, Sensitivity, VerificationState
from ayin.safety.visibility import visible_findings
from tests.test_auth import FAKE_PASSWORD, RecordingSender

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class RecordingSms:
    def __init__(self):
        self.sent: list[dict] = []

    def send_otp(self, *, to: str, code: str) -> None:
        self.sent.append({"to": to, "code": code})


class FailingSender:
    """A box with no reachable SMTP raises OSError on send. Regression guard for
    the prod bug where that 500'd the whole add and lost the identifier."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        raise OSError("SMTP unreachable (test)")


@pytest.fixture()
def sender():
    return RecordingSender()


@pytest.fixture()
def sms():
    return RecordingSms()


@pytest.fixture()
def client(sender, sms):
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: sender
    app.dependency_overrides[get_sms_sender] = lambda: sms
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def signed_up(client, unique_email):
    res = client.post(
        "/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD}
    )
    assert res.status_code == 201
    return res.json()


def test_signup_seeds_account_email_identifier(client, signed_up, unique_email):
    rows = client.get("/identifiers").json()
    assert len(rows) == 1
    assert rows[0]["kind"] == "email"
    assert rows[0]["value"] == unique_email
    assert rows[0]["verification_state"] == "unverified"
    assert rows[0]["challengeable"] is True


def test_account_email_verification_verifies_seed(client, sender, signed_up):
    token = sender.last_link_token()
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    rows = client.get("/identifiers").json()
    assert rows[0]["verification_state"] == "verified"
    assert rows[0]["verified_at"] is not None


def test_add_second_email_uses_identifier_link_flow(client, sender, signed_up):
    res = client.post(
        "/identifiers", json={"kind": "email", "value": "Second.Fake@Example.ORG"}
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["verification_state"] == "pending"  # challenge auto-sent

    assert sender.sent[-1]["to"] == "second.fake@example.org"  # normalized
    token = sender.last_link_token()
    ok = client.post("/identifiers/verify-email", json={"token": token})
    assert ok.status_code == 200

    rows = {r["value"]: r for r in client.get("/identifiers").json()}
    assert rows["Second.Fake@Example.ORG"]["verification_state"] == "verified"


def test_add_email_survives_send_failure(client, signed_up):
    """Regression: a box with no reachable SMTP must NOT 500 the add or lose the
    identifier. The row is created (unverified) and challenge_sent reports False
    so the UI can prompt a retry."""
    client.app.dependency_overrides[get_email_sender] = lambda: FailingSender()
    res = client.post("/identifiers", json={"kind": "email", "value": "newfake@example.org"})
    assert res.status_code == 201, res.text  # NOT 500
    body = res.json()
    assert body["challenge_sent"] is False
    assert body["verification_state"] == "unverified"
    rows = {r["value"]: r for r in client.get("/identifiers").json()}
    assert "newfake@example.org" in rows  # really persisted


def test_add_email_reports_challenge_sent_true_on_success(client, signed_up):
    """The happy path sets challenge_sent True so the UI shows 'email sent'."""
    res = client.post("/identifiers", json={"kind": "email", "value": "ok@example.org"})
    assert res.status_code == 201, res.text
    assert res.json()["challenge_sent"] is True
    assert res.json()["verification_state"] == "pending"


def test_phone_otp_flow(client, sms, signed_up):
    res = client.post("/identifiers", json={"kind": "phone", "value": "+1 (555) 010-4477"})
    assert res.status_code == 201, res.text
    ident_id = res.json()["id"]
    assert res.json()["verification_state"] == "pending"
    assert len(sms.sent) == 1
    code = sms.sent[0]["code"]

    bad = client.post(f"/identifiers/{ident_id}/verify-otp", json={"code": "000000"})
    assert bad.status_code == 400 or code == "000000"

    ok = client.post(f"/identifiers/{ident_id}/verify-otp", json={"code": code})
    assert ok.status_code == 200
    rows = {r["id"]: r for r in client.get("/identifiers").json()}
    assert rows[ident_id]["verification_state"] == "verified"


def test_otp_attempt_cap(client, sms, signed_up):
    res = client.post("/identifiers", json={"kind": "phone", "value": "+15550104478"})
    ident_id = res.json()["id"]
    code = sms.sent[-1]["code"]
    wrong = "999999" if code != "999999" else "111111"
    for _ in range(5):
        client.post(f"/identifiers/{ident_id}/verify-otp", json={"code": wrong})
    # attempts exhausted: even the right code is now rejected
    res = client.post(f"/identifiers/{ident_id}/verify-otp", json={"code": code})
    assert res.status_code == 400


def test_auxiliary_kinds_not_challengeable(client, signed_up):
    res = client.post("/identifiers", json={"kind": "username", "value": "fake_handle_77"})
    assert res.status_code == 201
    body = res.json()
    assert body["challengeable"] is False
    assert body["verification_state"] == "unverified"
    challenge = client.post(f"/identifiers/{body['id']}/send-challenge")
    assert challenge.status_code == 400


@pytest.mark.parametrize(
    "kind,value",
    [
        ("email", "not-an-email"),
        ("phone", "12"),
        ("username", "***bad***"),
        ("dna_sample", "acgt"),
    ],
)
def test_invalid_identifiers_rejected(client, signed_up, kind, value):
    res = client.post("/identifiers", json={"kind": kind, "value": value})
    assert res.status_code == 422


def test_duplicate_identifier_conflicts(client, signed_up):
    p = {"kind": "username", "value": "fake_dupe"}
    assert client.post("/identifiers", json=p).status_code == 201
    assert client.post("/identifiers", json=p).status_code == 409


def test_isolation_foreign_identifier_is_404(client, sender, signed_up, unique_email):
    mine = client.get("/identifiers").json()[0]["id"]

    client.cookies.clear()
    other_email = "other-" + unique_email
    client.post("/auth/signup", json={"email": other_email, "password": FAKE_PASSWORD})

    # B cannot see, challenge, verify, or delete A's identifier.
    assert all(r["id"] != mine for r in client.get("/identifiers").json())
    assert client.post(f"/identifiers/{mine}/send-challenge").status_code == 404
    assert client.post(
        f"/identifiers/{mine}/verify-otp", json={"code": "123456"}
    ).status_code == 404
    assert client.delete(f"/identifiers/{mine}").status_code == 404


def test_listing_identifiers_writes_data_access_audit(client, db, signed_up):
    client.get("/identifiers")
    rows = db.execute(
        select(AuditRecord).where(AuditRecord.event_type == "data.access")
    ).scalars().all()
    assert any(r.resource == "identifiers" and r.purpose == "self-view" for r in rows)


def _mk_finding(db, scan, subject, ident_id, key):
    f = Finding(
        scan_id=scan.id,
        subject_id=subject.id,
        identifier_id=ident_id,
        category=FindingCategory.CREDENTIAL,
        sensitivity=Sensitivity.HIGH,
        source="fake_connector",
        source_name="Fake Source (fixture)",
        captured_at=NOW,
        confidence=0.95,
        summary="Clearly-fake fixture finding.",
        dedupe_key=key,
    )
    db.add(f)
    db.flush()
    return f


def test_unverified_identifier_findings_are_hidden(db):
    """The M0-4 acceptance gate, tested at the data layer that every findings
    endpoint must go through."""
    user = User(email=f"gate-{uuid.uuid4().hex[:8]}@example.org")
    db.add(user)
    db.flush()
    subject = Subject(owner_user_id=user.id)
    db.add(subject)
    db.flush()
    verified = Identifier(
        subject_id=subject.id, kind="email",
        value_raw="v@example.org", value_normalized="v@example.org",
        verification_state=VerificationState.VERIFIED, verified_at=NOW,
    )
    unverified = Identifier(
        subject_id=subject.id, kind="email",
        value_raw="u@example.org", value_normalized="u@example.org",
    )
    db.add_all([verified, unverified])
    db.flush()
    scan = Scan(requester_user_id=user.id, subject_id=subject.id)
    db.add(scan)
    db.flush()

    f_visible = _mk_finding(db, scan, subject, verified.id, "k1")
    f_hidden = _mk_finding(db, scan, subject, unverified.id, "k2")
    f_derived = _mk_finding(db, scan, subject, None, "k3")
    db.commit()

    ids = {f.id for f in visible_findings(db, subject.id)}
    assert f_visible.id in ids
    assert f_derived.id in ids
    assert f_hidden.id not in ids  # unverified seed → no sensitive results


def test_removing_identifier_cascades_findings(client, db, sender, signed_up):
    """Deleting a seed deletes its findings — minimize what we keep."""
    res = client.post("/identifiers", json={"kind": "email", "value": "gone@example.org"})
    ident_id = uuid.UUID(res.json()["id"])

    user = db.execute(select(User)).scalars().first()
    subject = db.execute(select(Subject).where(Subject.owner_user_id == user.id)).scalar_one()
    scan = Scan(requester_user_id=user.id, subject_id=subject.id)
    db.add(scan)
    db.flush()
    f = _mk_finding(db, scan, subject, ident_id, "kc")
    db.commit()
    fid = f.id

    assert client.delete(f"/identifiers/{ident_id}").status_code == 200
    db.expire_all()  # the API used its own session; drop our cached copies
    assert db.get(Finding, fid) is None
