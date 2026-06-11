"""M5-1 acceptance: invite-only beta gating.

- gate OFF (dev/test default): signup unchanged
- gate ON: signup requires a valid code; invalid/exhausted/revoked/expired
  codes refused with structured errors; redemption is atomic
- /config tells the frontend which mode it's in
- invite CLI functions create/list/revoke
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.beta.invites import InviteError, create_invites, redeem_invite, revoke_invite
from ayin.config import Settings, get_settings
from ayin.models import AnalyticsEvent, User
from ayin.models.invite import Invite
from tests.test_auth import FAKE_PASSWORD, RecordingSender


def _client(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_email_sender] = lambda: RecordingSender()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture()
def gated_client(db):
    settings = get_settings().model_copy(update={"beta_invite_required": True})
    return _client(settings)


def test_signup_without_gate_needs_no_invite(db, unique_email):
    client = _client(get_settings())
    res = client.post(
        "/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD}
    )
    assert res.status_code == 201


def test_gated_signup_requires_valid_invite(gated_client, db, unique_email):
    res = gated_client.post(
        "/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD}
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "INVITE_REQUIRED"

    res = gated_client.post(
        "/auth/signup",
        json={"email": unique_email, "password": FAKE_PASSWORD,
              "invite_code": "AYIN-NOPE-NOPE"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "INVITE_INVALID"

    invites = create_invites(db, count=1, max_uses=1, note="wave-1-test")
    db.commit()
    code = invites[0].code

    ok = gated_client.post(
        "/auth/signup",
        json={"email": unique_email, "password": FAKE_PASSWORD, "invite_code": code},
    )
    assert ok.status_code == 201
    db.expire_all()
    assert db.execute(select(Invite)).scalar_one().uses == 1
    assert db.execute(select(User).where(User.email == unique_email)).scalar_one()
    events = db.execute(select(AnalyticsEvent.name)).scalars().all()
    assert "invite_redeemed" in events

    # exhausted now
    again = gated_client.post(
        "/auth/signup",
        json={"email": "b-" + unique_email, "password": FAKE_PASSWORD, "invite_code": code},
    )
    assert again.status_code == 403
    assert "already been used" in again.json()["detail"]["message"]


def test_multi_use_revoke_and_expiry(db):
    invite = create_invites(db, count=1, max_uses=3, note="wave-multi")[0]
    db.commit()
    assert redeem_invite(db, invite.code).uses == 1
    assert redeem_invite(db, invite.code.lower()).uses == 2  # case-insensitive

    revoke_invite(db, invite.code)
    db.commit()
    with pytest.raises(InviteError, match="revoked"):
        redeem_invite(db, invite.code)

    expired = create_invites(db, count=1)[0]
    expired.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    with pytest.raises(InviteError, match="expired"):
        redeem_invite(db, expired.code)


def test_codes_are_readable_and_unique(db):
    invites = create_invites(db, count=20, note="wave-format")
    codes = {i.code for i in invites}
    assert len(codes) == 20
    for code in codes:
        assert code.startswith("AYIN-") and len(code) == 14
        for bad in "01OI":
            assert bad not in code.split("AYIN-")[1]


def test_config_endpoint_reflects_mode(db):
    plain = _client(get_settings())
    assert plain.get("/config").json()["beta_invite_required"] is False
    gated = _client(get_settings().model_copy(update={"beta_invite_required": True}))
    body = gated.get("/config").json()
    assert body["beta_invite_required"] is True
    assert body["tos_current_version"]
