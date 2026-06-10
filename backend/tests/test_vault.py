"""M1-5 acceptance: PII vault.

- sensitive fields are encrypted at rest (ciphertext bytes contain no plaintext)
- reading writes an audit record
- delete crypto-shreds the subject's key → items unreadable forever
- retention purge removes expired items
- orchestrator routes connector sensitive_payload → vault, never findings

All payloads clearly fake.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from ayin.config import get_settings
from ayin.connectors import (
    AccessMethod,
    Connector,
    ConnectorRegistry,
    NormalizedFinding,
    RawResult,
    SourceGovernance,
)
from ayin.models import AuditRecord, Finding, Subject, User, VaultItem, VaultKey
from ayin.models.enums import FindingCategory, IdentifierKind, Sensitivity
from ayin.safety.audit import user_actor
from ayin.vault.store import DbVault, VaultNotConfigured, _master_key, purge_expired

FAKE_SECRET_PAYLOAD = {"leaked_hint": "fixture-secret-NOT-REAL-xyzzy", "classes": ["fake"]}


@pytest.fixture()
def subject(db):
    u = User(email=f"vault-{uuid.uuid4().hex[:8]}@example.org")
    db.add(u)
    db.flush()
    s = Subject(owner_user_id=u.id)
    db.add(s)
    db.flush()
    db.commit()
    return s


@pytest.fixture()
def vault():
    return DbVault(get_settings())


def test_round_trip_and_encrypted_at_rest(db, subject, vault):
    ref = vault.put(db, subject_id=subject.id, kind="finding.credential",
                    payload=FAKE_SECRET_PAYLOAD)
    db.commit()

    item = db.execute(select(VaultItem)).scalar_one()
    at_rest = bytes(item.ciphertext) + bytes(item.nonce)
    assert b"fixture-secret-NOT-REAL-xyzzy" not in at_rest  # truly encrypted
    assert b"leaked_hint" not in at_rest

    out = vault.get(db, subject_id=subject.id, ref=ref,
                    actor=user_actor(subject.owner_user_id), purpose="self-view")
    db.commit()
    assert out == FAKE_SECRET_PAYLOAD


def test_every_read_is_audited(db, subject, vault):
    ref = vault.put(db, subject_id=subject.id, kind="finding.credential",
                    payload=FAKE_SECRET_PAYLOAD)
    vault.get(db, subject_id=subject.id, ref=ref,
              actor=user_actor(subject.owner_user_id), purpose="self-view")
    db.commit()
    access = db.execute(
        select(AuditRecord).where(AuditRecord.event_type == "data.access")
    ).scalars().all()
    assert any(
        r.resource == "vault.finding.credential" and r.purpose == "self-view"
        and r.detail.get("ref") == ref
        for r in access
    )
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "vault.stored" in events


def test_wrong_subject_cannot_read(db, subject, vault):
    ref = vault.put(db, subject_id=subject.id, kind="x", payload={"fake": 1})
    db.commit()
    other = uuid.uuid4()
    assert vault.get(db, subject_id=other, ref=ref,
                     actor=user_actor(other), purpose="self-view") is None


def test_crypto_shred_makes_items_unreadable(db, subject, vault):
    ref = vault.put(db, subject_id=subject.id, kind="x", payload=FAKE_SECRET_PAYLOAD)
    db.commit()

    destroyed = vault.shred_subject(
        db, subject_id=subject.id, actor=user_actor(subject.owner_user_id)
    )
    db.commit()
    assert destroyed == 1
    key = db.execute(select(VaultKey).where(VaultKey.subject_id == subject.id)).scalar_one()
    assert key.wrapped_dek is None
    assert key.destroyed_at is not None
    assert vault.get(db, subject_id=subject.id, ref=ref,
                     actor=user_actor(subject.owner_user_id), purpose="self-view") is None
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "vault.shredded" in events

    # life after shred: new data gets a fresh key and works
    ref2 = vault.put(db, subject_id=subject.id, kind="x", payload={"fresh": True})
    db.commit()
    assert vault.get(db, subject_id=subject.id, ref=ref2,
                     actor=user_actor(subject.owner_user_id), purpose="self-view") == {
        "fresh": True
    }


def test_retention_purge(db, subject, vault):
    ref = vault.put(db, subject_id=subject.id, kind="x", payload={"fake": 1},
                    retention_days=30)
    item = db.execute(select(VaultItem)).scalar_one()
    item.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    assert purge_expired(db) == 1
    assert db.execute(select(VaultItem)).scalar_one_or_none() is None
    assert vault.get(db, subject_id=subject.id, ref=ref,
                     actor=user_actor(subject.owner_user_id), purpose="self-view") is None
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "vault.purged" in events


def test_expired_item_not_returned_even_before_purge(db, subject, vault):
    ref = vault.put(db, subject_id=subject.id, kind="x", payload={"fake": 1})
    item = db.execute(select(VaultItem)).scalar_one()
    item.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert vault.get(db, subject_id=subject.id, ref=ref,
                     actor=user_actor(subject.owner_user_id), purpose="self-view") is None


def test_production_requires_master_key():
    prod = get_settings().model_copy(
        update={"app_env": "production", "vault_master_key": ""}
    )
    with pytest.raises(VaultNotConfigured):
        _master_key(prod)


def test_invalid_master_key_rejected():
    bad = get_settings().model_copy(update={"vault_master_key": "dG9vLXNob3J0"})
    with pytest.raises(VaultNotConfigured):
        _master_key(bad)


# ── Orchestrator wiring ──────────────────────────────────────────────


class SensitiveConnector(Connector):
    """Fixture connector that emits a sensitive payload (vault-bound)."""

    id = "sensitive_fixture"
    name = "Sensitive Fixture Source"
    version = "0.0.1"
    governance = SourceGovernance(
        legal_basis="Synthetic fixture data for vault wiring tests.",
        access_method=AccessMethod.SYNTHETIC,
        tos_ref="n/a",
        data_classes=["fixture"],
        cost_per_call_usd=0.0,
        rate_limit_per_minute=600,
        counsel_signoff=False,
    )
    supported_kinds = frozenset({IdentifierKind.EMAIL})

    def authenticate(self): ...

    def fetch(self, seed):
        return [RawResult(payload={}, fetched_at=datetime.now(timezone.utc))]

    def normalize(self, seed, raw):
        return [
            NormalizedFinding(
                category=FindingCategory.CREDENTIAL,
                sensitivity=Sensitivity.CRITICAL,
                source=self.id,
                source_name=self.name,
                captured_at=datetime.now(timezone.utc),
                confidence=0.9,
                summary="(FAKE) credential exposure with vault-bound detail",
                payload={"public_part": "ok"},
                sensitive_payload=FAKE_SECRET_PAYLOAD,
                dedupe_key=f"sensitive:{seed.value}",
                identifier_id=seed.identifier_id,
            )
        ]


def test_orchestrator_routes_sensitive_payload_to_vault(db, vault):
    from ayin.orchestrator import engine
    from tests.test_orchestrator import _mk_user

    reg = ConnectorRegistry()
    reg.register(SensitiveConnector)
    reg.enable("sensitive_fixture", environment="test")

    user = _mk_user(db, with_aux=False)
    scan, _ = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=reg, vault=vault, inline=True
    )
    finding = db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalar_one()
    assert finding.vault_ref is not None
    assert "fixture-secret-NOT-REAL-xyzzy" not in str(finding.payload)
    assert "fixture-secret-NOT-REAL-xyzzy" not in finding.summary

    out = vault.get(db, subject_id=finding.subject_id, ref=finding.vault_ref,
                    actor=user_actor(user.id), purpose="test-verify")
    assert out == FAKE_SECRET_PAYLOAD


def test_null_vault_drops_sensitive_payload(db):
    """Pre-vault behavior must fail closed: drop, never store plaintext."""
    from ayin.orchestrator import engine
    from ayin.vault import NullVault
    from tests.test_orchestrator import _mk_user

    reg = ConnectorRegistry()
    reg.register(SensitiveConnector)  # fresh registry instance is fine
    reg.enable("sensitive_fixture", environment="test")

    user = _mk_user(db, with_aux=False)
    scan, _ = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=reg, vault=NullVault(),
        inline=True,
    )
    finding = db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalar_one()
    assert finding.vault_ref is None
    assert "fixture-secret-NOT-REAL-xyzzy" not in str(finding.payload)
    assert db.execute(select(VaultItem)).scalar_one_or_none() is None
