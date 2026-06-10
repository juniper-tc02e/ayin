"""M1-6 acceptance: rate/volume enforcement.

- exceeding a cap blocks with a clear message (429 at the API)
- limits change via the policy ROW — effective immediately, no deploy
- repeated hammering raises a velocity AbuseSignal (FR-TS-2 telemetry)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AbuseSignal, RateLimitPolicy, User
from ayin.models.enums import AbuseSignalKind
from ayin.safety import limits
from ayin.vault import NullVault
from tests.test_auth import FAKE_PASSWORD, RecordingSender


@pytest.fixture()
def client():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: RecordingSender()
    app.dependency_overrides[get_registry] = lambda: reg
    app.dependency_overrides[get_vault] = lambda: NullVault()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ready_user(client, unique_email):
    sender = RecordingSender()
    client.app.dependency_overrides[get_email_sender] = lambda: sender
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    return unique_email


def _set_policy(db, **values):
    db.execute(update(RateLimitPolicy).where(RateLimitPolicy.scope == "free").values(**values))
    db.commit()


def test_policy_comes_from_seeded_db_row(db):
    policy = limits.get_policy(db, "free", get_settings())
    assert policy.scans_per_day == 5  # seeded by migration 0007 from env defaults
    assert policy.scan_burst == 2


def test_unknown_plan_falls_back_to_free_caps_never_uncapped(db):
    policy = limits.get_policy(db, "plan-that-does-not-exist", get_settings())
    assert policy.scans_per_day == 5


def test_daily_cap_blocks_with_clear_message(client, db, ready_user):
    _set_policy(db, scans_per_day=1, scan_burst=10, burst_window_minutes=10)
    assert client.post("/scans").status_code == 202
    res = client.post("/scans")
    assert res.status_code == 429
    assert "Daily scan limit reached (1 per 24h)" in res.json()["detail"]["reason"]


def test_policy_change_applies_immediately_without_deploy(client, db, ready_user):
    _set_policy(db, scans_per_day=1, scan_burst=10, burst_window_minutes=10)
    assert client.post("/scans").status_code == 202
    assert client.post("/scans").status_code == 429  # capped at 1

    _set_policy(db, scans_per_day=10)  # support raises the cap — no restart
    assert client.post("/scans").status_code == 202


def test_burst_cap_independent_of_daily(client, db, ready_user):
    _set_policy(db, scans_per_day=100, scan_burst=2, burst_window_minutes=10)
    assert client.post("/scans").status_code == 202
    assert client.post("/scans").status_code == 202
    res = client.post("/scans")
    assert res.status_code == 429
    assert "Too many scans at once" in res.json()["detail"]["reason"]


def test_hammering_writes_velocity_abuse_signal(client, db, ready_user):
    _set_policy(db, scans_per_day=1, scan_burst=1, burst_window_minutes=60)
    client.post("/scans")  # allowed
    for _ in range(4):  # then hammer
        assert client.post("/scans").status_code == 429

    user = db.execute(select(User)).scalars().first()
    signals = db.execute(
        select(AbuseSignal).where(
            AbuseSignal.user_id == user.id, AbuseSignal.kind == AbuseSignalKind.VELOCITY
        )
    ).scalars().all()
    assert len(signals) == 1  # raised once per window, not per refusal
    assert signals[0].detail["refusals_in_window"] >= 3
