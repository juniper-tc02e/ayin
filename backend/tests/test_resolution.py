"""M2-1 + M2-2 acceptance: entity resolution.

M2-2: duplicates collapse with sources preserved; conflicts flagged, not
silently merged; every finding keeps category + sensitivity.
M2-1: same-person records merge above threshold; below-threshold shown as
"possible, unconfirmed"; user can confirm/reject; FALSE-MERGE RATE measured
against a labeled synthetic set.

All data clearly fake.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from ayin.models import AuditRecord, Finding, Identifier, Scan, Subject, User
from ayin.models.enums import (
    FindingCategory,
    FindingState,
    IdentifierKind,
    MatchStatus,
    Sensitivity,
    VerificationState,
)
from ayin.resolution.canonical import canonical_exposure_key, normalize_url
from ayin.resolution.engine import AUTO_MATCH_THRESHOLD, resolve_scan
from ayin.resolution.feedback import confirm_finding, reject_finding

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def ctx(db):
    """user + subject + verified email + unverifiable username/name seeds + scan."""
    user = User(email=f"er-{uuid.uuid4().hex[:8]}@example.org")
    db.add(user)
    db.flush()
    subject = Subject(owner_user_id=user.id)
    db.add(subject)
    db.flush()
    email = Identifier(
        subject_id=subject.id, kind=IdentifierKind.EMAIL,
        value_raw=user.email, value_normalized=user.email,
        verification_state=VerificationState.VERIFIED, verified_at=NOW,
    )
    username = Identifier(
        subject_id=subject.id, kind=IdentifierKind.USERNAME,
        value_raw="fake_handle", value_normalized="fake_handle",
    )
    name = Identifier(
        subject_id=subject.id, kind=IdentifierKind.FULL_NAME,
        value_raw="Fake Person", value_normalized="fake person",
    )
    db.add_all([email, username, name])
    db.flush()
    scan = Scan(requester_user_id=user.id, subject_id=subject.id)
    db.add(scan)
    db.flush()
    db.commit()
    return {"user": user, "subject": subject, "scan": scan,
            "email": email, "username": username, "name": name}


def _finding(db, ctx, *, source="src_a", category=FindingCategory.SOCIAL,
             confidence=0.5, url=None, payload=None, ident=None, key=None,
             sensitivity=Sensitivity.LOW):
    f = Finding(
        scan_id=ctx["scan"].id,
        subject_id=ctx["subject"].id,
        identifier_id=(ident.id if ident is not None else None),
        category=category,
        sensitivity=sensitivity,
        source=source,
        source_name=f"{source} (fixture)",
        source_url=url,
        captured_at=NOW,
        confidence=confidence,
        summary="Clearly-fake fixture finding.",
        payload=payload or {},
        dedupe_key=key or f"{source}:{uuid.uuid4().hex[:10]}",
    )
    db.add(f)
    db.flush()
    return f


# ── Canonical keys / URL normalization ───────────────────────────────


def test_url_normalization():
    assert normalize_url("HTTP://WWW.Social.Example/@handle/?utm_source=x&b=1#frag") == \
        "https://social.example/@handle?b=1"
    assert normalize_url("https://social.example/@handle") == \
        normalize_url("http://www.social.example/@handle/")


# ── M2-2: dedupe with sources preserved + conflicts flagged ──────────


def test_duplicates_collapse_preserving_sources(db, ctx):
    a = _finding(db, ctx, source="search_a", confidence=0.7,
                 url="https://social.example/@fake_handle", ident=ctx["email"])
    b = _finding(db, ctx, source="search_b", confidence=0.6,
                 url="http://www.social.example/@fake_handle/", ident=ctx["username"])
    db.commit()

    resolve_scan(db, ctx["scan"])
    db.commit()
    db.expire_all()

    a, b = db.get(Finding, a.id), db.get(Finding, b.id)
    assert a.state == FindingState.ACTIVE  # higher confidence → primary
    assert b.state == FindingState.SUPPRESSED
    assert b.duplicate_of == a.id
    assert {m["source"] for m in a.merged_sources} == {"search_a", "search_b"}
    assert a.corroboration_count == 2
    # category + sensitivity still present on every finding (FR-ER-2)
    assert a.category and a.sensitivity and b.category and b.sensitivity


def test_conflicting_data_flagged_not_silently_merged(db, ctx):
    _finding(db, ctx, source="breach_a", category=FindingCategory.CREDENTIAL,
             confidence=0.95, ident=ctx["email"], sensitivity=Sensitivity.CRITICAL,
             payload={"breach_name": "FakeBreach", "breach_date": "2024-01-01"})
    _finding(db, ctx, source="breach_b", category=FindingCategory.CREDENTIAL,
             confidence=0.75, ident=ctx["email"], sensitivity=Sensitivity.CRITICAL,
             payload={"breach_name": "FakeBreach", "breach_date": "2023-06-30"})
    db.commit()

    resolve_scan(db, ctx["scan"])
    db.commit()

    primary = db.execute(
        select(Finding).where(Finding.state == FindingState.ACTIVE)
    ).scalar_one()
    conflicts = primary.resolution["conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "breach_date"
    values = {v["value"] for v in conflicts[0]["values"]}
    assert values == {"'2024-01-01'", "'2023-06-30'"}
    # primary's own payload value untouched — no silent overwrite
    assert primary.payload["breach_date"] == "2024-01-01"


def test_distinct_exposures_do_not_collapse(db, ctx):
    _finding(db, ctx, url="https://social.example/@fake_handle", ident=ctx["email"])
    _finding(db, ctx, url="https://other.example/profile/fake", ident=ctx["email"])
    db.commit()
    summary = resolve_scan(db, ctx["scan"])
    assert summary["duplicates_collapsed"] == 0


def test_rerun_is_idempotent(db, ctx):
    _finding(db, ctx, source="a", confidence=0.7, url="https://x.example/p", ident=ctx["email"])
    _finding(db, ctx, source="b", confidence=0.6, url="https://x.example/p", ident=ctx["email"])
    db.commit()
    s1 = resolve_scan(db, ctx["scan"])
    db.commit()
    s2 = resolve_scan(db, ctx["scan"])  # resume / re-run
    db.commit()
    assert s1["duplicates_collapsed"] == 1
    assert s2["duplicates_collapsed"] == 0  # suppressed rows aren't re-processed
    actives = db.execute(
        select(Finding).where(Finding.state == FindingState.ACTIVE)
    ).scalars().all()
    assert len(actives) == 1


# ── M2-1: thresholds, the anti-namesake cap, user decisions ──────────


def test_verified_email_keyed_findings_auto_match(db, ctx):
    f = _finding(db, ctx, confidence=0.75, ident=ctx["email"],
                 url="https://social.example/@me")
    db.commit()
    resolve_scan(db, ctx["scan"])
    db.commit()
    db.expire_all()
    f = db.get(Finding, f.id)
    assert f.match_status == MatchStatus.AUTO_MATCHED
    assert f.match_confidence >= AUTO_MATCH_THRESHOLD
    assert "control-verified" in " ".join(f.resolution["match_reasons"])


def test_single_source_name_match_can_never_auto_merge(db, ctx):
    """The anti-namesake wall: even a connector claiming 0.99 confidence on a
    name-keyed finding stays 'possible' without corroboration."""
    f = _finding(db, ctx, confidence=0.99, ident=ctx["name"],
                 url="https://news.example/story-about-some-fake-person")
    db.commit()
    resolve_scan(db, ctx["scan"])
    db.commit()
    db.expire_all()
    f = db.get(Finding, f.id)
    assert f.match_status == MatchStatus.POSSIBLE  # shown as possible, unconfirmed
    assert f.match_confidence < AUTO_MATCH_THRESHOLD
    assert any("capped" in r for r in f.resolution["match_reasons"])


def test_corroboration_lifts_unverifiable_seeds_over_threshold(db, ctx):
    a = _finding(db, ctx, source="src_a", confidence=0.6, ident=ctx["username"],
                 url="https://social.example/@fake_handle")
    _finding(db, ctx, source="src_b", confidence=0.5, ident=ctx["username"],
             url="https://social.example/@fake_handle")
    db.commit()
    resolve_scan(db, ctx["scan"])
    db.commit()
    db.expire_all()
    a = db.get(Finding, a.id)
    assert a.corroboration_count == 2
    assert a.match_status == MatchStatus.AUTO_MATCHED  # 0.6→cap 0.6 +0.15 = 0.75
    assert a.match_confidence == pytest.approx(0.75, abs=0.001)


def test_user_confirm_and_reject_are_final(db, ctx):
    f = _finding(db, ctx, confidence=0.5, ident=ctx["name"],
                 url="https://blog.example/fake-person")
    db.commit()
    resolve_scan(db, ctx["scan"])
    db.commit()
    db.expire_all()
    f = db.get(Finding, f.id)
    assert f.match_status == MatchStatus.POSSIBLE

    confirm_finding(db, ctx["user"], f)
    db.commit()
    assert f.match_status == MatchStatus.CONFIRMED

    resolve_scan(db, ctx["scan"])  # re-resolution must NOT overwrite the user
    db.commit()
    db.expire_all()
    f = db.get(Finding, f.id)
    assert f.match_status == MatchStatus.CONFIRMED

    reject_finding(db, ctx["user"], f)
    db.commit()
    assert f.match_status == MatchStatus.REJECTED
    events = db.execute(select(AuditRecord.event_type)).scalars().all()
    assert "resolution.confirmed" in events
    assert "resolution.rejected" in events


# ── M2-1 acceptance: false-merge rate measured ───────────────────────


def test_false_merge_rate_on_labeled_synthetic_set(db, ctx):
    """Labeled fixture population: is_me findings (email-keyed, corroborated
    username) and namesake findings (name/username-keyed, single-source,
    even with inflated connector confidence). The matcher must auto-merge
    ZERO namesakes; recall on true matches stays useful."""
    labeled: list[tuple[Finding, bool]] = []

    # genuinely-me: email-keyed (verified control)
    for i, conf in enumerate([0.95, 0.8, 0.75]):
        f = _finding(db, ctx, source=f"me_src_{i}", confidence=conf,
                     ident=ctx["email"], url=f"https://site{i}.example/me")
        labeled.append((f, True))
    # genuinely-me: username corroborated across two sources
    u1 = _finding(db, ctx, source="ua", confidence=0.6, ident=ctx["username"],
                  url="https://social.example/@fake_handle")
    _finding(db, ctx, source="ub", confidence=0.55, ident=ctx["username"],
             url="https://social.example/@fake_handle")
    labeled.append((u1, True))

    # namesakes: single-source name/username findings, some with inflated confidence
    namesakes = []
    for i, conf in enumerate([0.99, 0.8, 0.65, 0.5, 0.45]):
        f = _finding(db, ctx, source=f"ns_src_{i}", confidence=conf,
                     ident=ctx["name"] if i % 2 else ctx["username"],
                     url=f"https://namesake{i}.example/profile")
        namesakes.append(f)
        labeled.append((f, False))

    db.commit()
    resolve_scan(db, ctx["scan"])
    db.commit()
    db.expire_all()

    auto_ids = {
        f.id
        for f in db.execute(
            select(Finding).where(Finding.match_status == MatchStatus.AUTO_MATCHED)
        ).scalars()
    }
    not_me = [f for f, is_me in labeled if not is_me]
    me = [f for f, is_me in labeled if is_me]

    false_merges = sum(1 for f in not_me if f.id in auto_ids)
    false_merge_rate = false_merges / len(not_me)
    recall = sum(1 for f in me if f.id in auto_ids) / len(me)

    print(f"\nfalse-merge rate: {false_merge_rate:.0%} ({false_merges}/{len(not_me)}) | "
          f"recall on true matches: {recall:.0%}")
    assert false_merge_rate == 0.0  # the enemy (PRD FR-ER-1) — structurally blocked
    assert recall == 1.0  # and we still catch everything genuinely the user's
