"""UF5 — username ownership verification (bio-code), tier wiring, and the
resolution bypass for a proven-owned handle. All data clearly fake."""

import uuid
from datetime import datetime, timezone

import httpx
import pytest

from ayin.config import get_settings
from ayin.connectors.username.connector import UsernameFootprintConnector
from ayin.connectors.username.verification import (
    UsernameVerificationError,
    challenge_code,
    profile_proves_ownership,
    verify_and_record,
)
from ayin.models import Finding, Identifier, Scan, Subject, User
from ayin.models.enums import (
    FindingCategory,
    IdentifierKind,
    MatchStatus,
    Sensitivity,
    VerificationState,
)
from ayin.orchestrator.engine import build_seed_queries
from ayin.resolution.engine import resolve_scan

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ── challenge code (pure, stateless) ─────────────────────────────────

def test_challenge_code_is_deterministic_and_per_identifier():
    s = get_settings()
    a, b = uuid.uuid4(), uuid.uuid4()
    assert challenge_code(a, s) == challenge_code(a, s)   # stable across retries
    assert challenge_code(a, s) != challenge_code(b, s)   # bound to the identifier
    assert challenge_code(a, s).startswith("ayin-verify-")


# ── profile proof (mock transport) ───────────────────────────────────

def test_profile_proves_ownership_present_vs_absent():
    code = "ayin-verify-abc123def456"
    with _client(lambda r: httpx.Response(200, text=f"<bio>{code} hi</bio>")) as c:
        assert profile_proves_ownership("https://x.test/me", code, c) is True
    with _client(lambda r: httpx.Response(200, text="nothing here")) as c:
        assert profile_proves_ownership("https://x.test/me", code, c) is False


def test_profile_proof_raises_on_non_200_or_transport_error():
    with _client(lambda r: httpx.Response(404)) as c:
        with pytest.raises(UsernameVerificationError):
            profile_proves_ownership("https://x.test/me", "code", c)

    def boom(r):
        raise httpx.ConnectError("down")

    with _client(boom) as c:
        with pytest.raises(UsernameVerificationError):
            profile_proves_ownership("https://x.test/me", "code", c)


# ── verify_and_record marks the identifier verified (DB) ─────────────

@pytest.fixture()
def uctx(db):
    user = User(email=f"v-{uuid.uuid4().hex[:8]}@example.org")
    db.add(user)
    db.flush()
    subject = Subject(owner_user_id=user.id)
    db.add(subject)
    db.flush()
    username = Identifier(
        subject_id=subject.id, kind=IdentifierKind.USERNAME,
        value_raw="ayindemo", value_normalized="ayindemo",
    )
    db.add(username)
    db.flush()
    db.commit()
    return {"user": user, "subject": subject, "username": username}


def test_verify_and_record_marks_verified_on_success(db, uctx):
    s = get_settings()
    code = challenge_code(uctx["username"].id, s)
    with _client(lambda r: httpx.Response(200, text=f"<bio>{code}</bio>")) as c:
        ok = verify_and_record(db, uctx["username"], "https://github.com/ayindemo", s, client=c)
    assert ok is True
    db.refresh(uctx["username"])
    assert uctx["username"].verification_state is VerificationState.VERIFIED
    assert uctx["username"].verified_at is not None


def test_verify_and_record_leaves_unverified_on_wrong_code(db, uctx):
    s = get_settings()
    with _client(lambda r: httpx.Response(200, text="some other text")) as c:
        ok = verify_and_record(db, uctx["username"], "https://github.com/ayindemo", s, client=c)
    assert ok is False
    db.refresh(uctx["username"])
    assert uctx["username"].verification_state is VerificationState.UNVERIFIED


def test_verify_and_record_rejects_non_username(db, uctx):
    s = get_settings()
    email = Identifier(
        subject_id=uctx["subject"].id, kind=IdentifierKind.EMAIL,
        value_raw="x@example.org", value_normalized="x@example.org",
    )
    db.add(email)
    db.flush()
    with pytest.raises(UsernameVerificationError):
        verify_and_record(db, email, "https://x.test", s)  # no client → must raise before fetch


# ── orchestrator: ownership_tier rides from verification state ────────

def test_build_seed_queries_sets_ownership_tier(db, uctx):
    seeds = build_seed_queries([uctx["username"]], UsernameFootprintConnector)
    assert seeds[0].context["ownership_tier"] == "asserted"

    uctx["username"].verification_state = VerificationState.VERIFIED
    db.flush()
    seeds2 = build_seed_queries([uctx["username"]], UsernameFootprintConnector)
    assert seeds2[0].context["ownership_tier"] == "verified"


# ── resolution: a proven-owned handle bypasses the anti-namesake cap ─

def test_verified_username_finding_auto_matches(db, uctx):
    uctx["username"].verification_state = VerificationState.VERIFIED
    db.flush()
    scan = Scan(requester_user_id=uctx["user"].id, subject_id=uctx["subject"].id)
    db.add(scan)
    db.flush()
    f = Finding(
        scan_id=scan.id, subject_id=uctx["subject"].id, identifier_id=uctx["username"].id,
        category=FindingCategory.SOCIAL, sensitivity=Sensitivity.MEDIUM,
        source="username_footprint", source_name="Username Footprint",
        source_url="https://github.com/ayindemo", captured_at=NOW, confidence=0.85,
        summary="fixture", payload={"site_id": "github"},
        dedupe_key="username_footprint:github:ayindemo",
    )
    db.add(f)
    db.flush()
    resolve_scan(db, scan)
    db.refresh(f)
    # proven-owned (verified) → not a namesake → cap lifted → auto-matched
    assert f.match_status is MatchStatus.AUTO_MATCHED
    assert f.match_confidence >= 0.70


def test_unverified_username_finding_stays_possible(db, uctx):
    # same finding, but the username is NOT verified → capped → possible
    scan = Scan(requester_user_id=uctx["user"].id, subject_id=uctx["subject"].id)
    db.add(scan)
    db.flush()
    f = Finding(
        scan_id=scan.id, subject_id=uctx["subject"].id, identifier_id=uctx["username"].id,
        category=FindingCategory.SOCIAL, sensitivity=Sensitivity.MEDIUM,
        source="username_footprint", source_name="Username Footprint",
        source_url="https://github.com/ayindemo", captured_at=NOW, confidence=0.85,
        summary="fixture", payload={"site_id": "github"},
        dedupe_key="username_footprint:github:ayindemo",
    )
    db.add(f)
    db.flush()
    resolve_scan(db, scan)
    db.refresh(f)
    assert f.match_status is MatchStatus.POSSIBLE
    assert f.match_confidence <= 0.65
