"""M3-5 acceptance: delete-everything + data-subject access.

- delete removes/shreds all subject data and confirms
- the audit chain survives intact (and contains the deletion events)
- re-auth required; login impossible afterwards; email freed for re-signup
- /account/summary shows what Ayin holds (FR-TS-4 'access', audited)
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
from ayin.models import (
    AuditRecord,
    Finding,
    Identifier,
    Scan,
    Score,
    Subject,
    User,
    VaultItem,
)
from ayin.safety.audit import verify_chain
from ayin.vault.store import DbVault
from tests.test_auth import FAKE_PASSWORD, RecordingSender


@pytest.fixture()
def sender():
    return RecordingSender()


@pytest.fixture()
def client(sender):
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: sender
    app.dependency_overrides[get_registry] = lambda: reg
    app.dependency_overrides[get_vault] = lambda: DbVault(get_settings())
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def scanned_user(client, sender, db, unique_email):
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})
    client.post("/scans")
    # put something in the vault too, so shred has substance
    subject = db.execute(select(Subject)).scalars().first()
    DbVault(get_settings()).put(
        db, subject_id=subject.id, kind="finding.credential",
        payload={"fake_sensitive": "fixture-value"},
    )
    db.commit()
    return unique_email


def test_summary_shows_what_ayin_holds(client, db, scanned_user):
    res = client.get("/account/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["identifiers"] >= 1
    assert body["scans"] == 1
    assert body["findings"] >= 2
    assert body["vault_items"] == 1
    assert body["pii_retention_days"] > 0
    access = db.execute(
        select(AuditRecord).where(AuditRecord.event_type == "data.access")
    ).scalars().all()
    assert any(r.resource == "account.summary" for r in access)


def test_delete_requires_correct_password(client, db, scanned_user):
    res = client.post("/account/delete", json={"password": "wrong-pass-entirely"})
    assert res.status_code == 401
    assert db.execute(select(User)).scalars().all()  # nothing deleted


def test_delete_everything_shreds_and_confirms(client, db, scanned_user):
    res = client.post("/account/delete", json={"password": FAKE_PASSWORD})
    assert res.status_code == 200
    msg = res.json()["message"]
    assert "crypto-shredded" in msg  # explicit confirmation (acceptance)

    db.expire_all()
    assert db.execute(select(User)).scalars().all() == []
    assert db.execute(select(Subject)).scalars().all() == []
    assert db.execute(select(Identifier)).scalars().all() == []
    assert db.execute(select(Scan)).scalars().all() == []
    assert db.execute(select(Finding)).scalars().all() == []
    assert db.execute(select(Score)).scalars().all() == []
    assert db.execute(select(VaultItem)).scalars().all() == []

    # the key row may cascade away with the subject — but the shred audit
    # event proves the key was destroyed BEFORE deletion
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "account.delete_requested" in events
    assert "vault.shredded" in events

    # the audit spine survives, chain intact, and holds no PII values
    ok, bad = verify_chain(db)
    assert ok and bad is None
    blob = " ".join(
        str(r.detail) for r in db.execute(select(AuditRecord)).scalars()
    )
    assert scanned_user not in blob  # the email value appears nowhere

    # session is dead and login impossible
    assert client.get("/auth/me").status_code == 401
    login = client.post(
        "/auth/login", json={"email": scanned_user, "password": FAKE_PASSWORD}
    )
    assert login.status_code == 401


def test_email_freed_for_resignup_after_delete(client, sender, scanned_user):
    client.post("/account/delete", json={"password": FAKE_PASSWORD})
    res = client.post(
        "/auth/signup", json={"email": scanned_user, "password": FAKE_PASSWORD}
    )
    assert res.status_code == 201  # a fresh start is genuinely fresh
