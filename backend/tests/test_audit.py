"""M0-6 acceptance: append-only, tamper-evident audit log.

- helpers write chained records
- records are not updatable/deletable through the app (DB trigger)
- silent tampering (trigger disabled by a privileged actor) is detected
"""

import uuid

import pytest
from sqlalchemy import text

from ayin.models import GENESIS_HASH, AuditRecord
from ayin.safety.audit import (
    record_data_access,
    record_event,
    record_scan_event,
    system_actor,
    user_actor,
    verify_chain,
)


def test_chain_links_and_verifies(db):
    uid = uuid.uuid4()
    sid = uuid.uuid4()
    r1 = record_event(db, actor=user_actor(uid), event_type="auth.signup")
    r2 = record_data_access(
        db, actor=user_actor(uid), subject_id=sid, resource="identifiers", purpose="self-view"
    )
    r3 = record_scan_event(
        db, actor=system_actor("orchestrator"), event_type="scan.created",
        scan_id=uuid.uuid4(), subject_id=sid,
    )
    db.commit()

    assert r1.prev_hash == GENESIS_HASH
    assert r2.prev_hash == r1.hash
    assert r3.prev_hash == r2.hash
    ok, bad = verify_chain(db)
    assert ok and bad is None


def test_scan_events_must_be_namespaced(db):
    with pytest.raises(ValueError):
        record_scan_event(
            db, actor=system_actor(), event_type="oops", scan_id=uuid.uuid4()
        )


def test_data_access_records_resource_and_purpose(db):
    sid = uuid.uuid4()
    rec = record_data_access(
        db, actor=user_actor(uuid.uuid4()), subject_id=sid,
        resource="findings.credential", purpose="self-view",
    )
    db.commit()
    assert rec.event_type == "data.access"
    assert rec.resource == "findings.credential"
    assert rec.purpose == "self-view"
    assert rec.subject_id == sid


def test_update_is_blocked_by_trigger(db, engine):
    record_event(db, actor=system_actor(), event_type="auth.signup")
    db.commit()
    with pytest.raises(Exception) as exc_info, engine.begin() as conn:
        conn.execute(text("UPDATE audit_records SET event_type = 'tampered'"))
    assert "append-only" in str(exc_info.value)


def test_delete_is_blocked_by_trigger(db, engine):
    record_event(db, actor=system_actor(), event_type="auth.signup")
    db.commit()
    with pytest.raises(Exception) as exc_info, engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_records"))
    assert "append-only" in str(exc_info.value)


def test_tampering_with_trigger_disabled_is_detected(db, engine):
    """Even a privileged actor who disables the trigger can't tamper silently:
    the hash chain breaks and verify_chain points at the record."""
    record_event(db, actor=system_actor(), event_type="auth.signup")
    record_event(db, actor=system_actor(), event_type="auth.login")
    db.commit()
    ok, _ = verify_chain(db)
    assert ok

    with engine.begin() as conn:  # superuser/owner-only path, simulating an attacker
        conn.execute(text("ALTER TABLE audit_records DISABLE TRIGGER trg_audit_records_immutable"))
        conn.execute(
            text("UPDATE audit_records SET event_type='auth.evil' "
                 "WHERE event_type='auth.login'")
        )
        conn.execute(text("ALTER TABLE audit_records ENABLE TRIGGER trg_audit_records_immutable"))

    ok, bad_id = verify_chain(db)
    assert not ok
    assert bad_id is not None


def test_audit_atomic_with_caller_transaction(db):
    """Rolling back the business action rolls back its audit record too."""
    record_event(db, actor=system_actor(), event_type="auth.signup")
    db.rollback()
    assert db.query(AuditRecord).count() == 0
