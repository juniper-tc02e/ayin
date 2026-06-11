"""M3-4 acceptance: "Exclude me from Ayin".

- verify identity → suppress as scan subject → purge cached data
- honored on future scans (excluded seed never fans out; excluded anchor
  refuses the scan with an honest reason)
- action audited — without ever logging the value
- the exclusions table stores hashes only (asserted)
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.models import AuditRecord, Finding, Identifier
from ayin.models.exclusion import Exclusion
from ayin.vault import NullVault
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
    app.dependency_overrides[get_vault] = lambda: NullVault()
    with TestClient(app) as c:
        yield c


def _ready_user(client, sender, email):
    client.post("/auth/signup", json={"email": email, "password": FAKE_PASSWORD})
    client.post("/auth/verify-email", json={"token": sender.last_link_token()})
    version = client.get("/tos").json()["current_version"]
    client.post("/tos/accept", json={"version": version})


def _exclude(client, sender, email):
    res = client.post("/exclusions/request", json={"kind": "email", "value": email})
    assert res.status_code == 200
    token = sender.last_link_token()
    res = client.post("/exclusions/confirm", json={"token": token})
    assert res.status_code == 200


def test_full_exclusion_flow_purges_and_audits(client, sender, db, unique_email):
    _ready_user(client, sender, unique_email)
    client.post("/scans")
    assert db.execute(select(Finding)).scalars().all()  # cached data exists

    client.cookies.clear()  # the public flow needs no session
    _exclude(client, sender, unique_email)

    # purge: the identifier and all findings keyed to it are gone
    # (the email was the only seed, so the whole scan's findings cascade away)
    db.expire_all()
    assert db.execute(
        select(Identifier).where(Identifier.value_normalized == unique_email)
    ).scalar_one_or_none() is None
    assert db.execute(select(Finding)).scalars().all() == []

    events = db.execute(select(AuditRecord)).scalars().all()
    types = [e.event_type for e in events]
    assert "exclusion.requested" in types
    assert "exclusion.confirmed" in types
    # the VALUE never appears in any audit detail
    blob = " ".join(str(e.detail) for e in events if e.event_type.startswith("exclusion"))
    assert unique_email not in blob


def test_exclusions_table_stores_hashes_only(client, sender, db, unique_email):
    client.post("/exclusions/request", json={"kind": "email", "value": unique_email})
    row = db.execute(select(Exclusion)).scalar_one()
    assert unique_email not in (row.value_hash or "")
    assert len(row.value_hash) == 64  # sha256 hex
    cols = {c["name"] for c in inspect(db.get_bind()).get_columns("exclusions")}
    assert "value" not in cols and "value_raw" not in cols  # no plaintext column
    raw = db.execute(text("SELECT exclusions::text FROM exclusions")).scalars().all()
    assert all(unique_email not in r for r in raw)


def test_excluded_identity_is_suppressed_in_subsequent_scans(client, sender, db, unique_email):
    """The acceptance core: after exclusion, the identity never scans again —
    even by the person themselves."""
    _ready_user(client, sender, unique_email)
    assert client.post("/scans").status_code == 202

    client.cookies.clear()
    _exclude(client, sender, unique_email)

    # log back in; the account still exists, but its anchor is excluded
    client.post("/auth/login", json={"email": unique_email, "password": FAKE_PASSWORD})
    res = client.post("/scans")
    assert res.status_code == 403  # subject_excluded maps to forbidden
    assert "subject_excluded" in res.json()["detail"]["reason"]
    assert "honored for everyone" in res.json()["detail"]["reason"]


def test_aux_seeds_alone_cannot_bypass_exclusion(client, sender, db, unique_email):
    _ready_user(client, sender, unique_email)
    client.post("/identifiers", json={"kind": "username", "value": "fake_bypass_handle"})
    client.cookies.clear()
    _exclude(client, sender, unique_email)
    client.post("/auth/login", json={"email": unique_email, "password": FAKE_PASSWORD})
    # username alone is no verified anchor → scan refused, nothing fans out
    res = client.post("/scans")
    assert res.status_code == 403
    assert "subject_excluded" in res.json()["detail"]["reason"]


def test_request_is_idempotent_and_oracle_free(client, sender, unique_email):
    r1 = client.post("/exclusions/request", json={"kind": "email", "value": unique_email})
    token = sender.last_link_token()
    client.post("/exclusions/confirm", json={"token": token})
    r2 = client.post("/exclusions/request", json={"kind": "email", "value": unique_email})
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()  # identical response either way


def test_resend_cooldown_prevents_email_bombing(client, sender, unique_email):
    client.post("/exclusions/request", json={"kind": "email", "value": unique_email})
    sent_after_first = len(sender.sent)
    for _ in range(5):
        client.post("/exclusions/request", json={"kind": "email", "value": unique_email})
    assert len(sender.sent) == sent_after_first  # cooldown swallowed the rest


def test_bad_token_and_unsupported_kind(client, unique_email):
    assert client.post(
        "/exclusions/confirm", json={"token": "x" * 43}
    ).status_code == 400
    res = client.post("/exclusions/request", json={"kind": "phone", "value": "+15550100000"})
    assert res.status_code == 422
    assert "email" in res.json()["detail"].lower()
