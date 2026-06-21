"""UF4 — username-footprint integration with resolution, scoring, remediation.

Proves the end-to-end contract: a username finding is anti-namesake-capped to
"possible" (never auto-merged), and once the user CONFIRMS it, it moves the score
and gets a concrete per-site removal step. All data clearly fake.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from ayin.models import Finding, Identifier, Scan, Subject, User
from ayin.models.enums import (
    FindingCategory,
    IdentifierKind,
    MatchStatus,
    Sensitivity,
    VerificationState,
)
from ayin.remediation.checklist import _item_for, build_checklist
from ayin.resolution.engine import resolve_scan
from ayin.scoring.engine import compute_score

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ── checklist item shaping (no DB) ───────────────────────────────────

def test_checklist_username_social_uses_per_site_opt_out():
    f = SimpleNamespace(
        id="x", category=FindingCategory.SOCIAL, sensitivity=Sensitivity.MEDIUM,
        payload={"site_id": "github", "site": "GitHub", "removable": True,
                 "opt_out_url": "https://github.com/settings/admin",
                 "opt_out_instructions": "Delete the account."},
    )
    item = _item_for(f, 5, elevated=False)
    assert "GitHub" in item.title
    assert any("Delete the account." in s for s in item.steps)
    assert any("github.com/settings/admin" in s for s in item.steps)
    assert item.category == "social"
    assert item.effort == "medium"


def test_checklist_linkage_item_shape():
    f = SimpleNamespace(
        id="y", category=FindingCategory.LINKAGE, sensitivity=Sensitivity.MEDIUM,
        payload={"kind": "handle_linkage", "handle": "ayindemo", "site_count": 4},
    )
    item = _item_for(f, 3, elevated=False)
    joined = " ".join(item.steps)
    assert "ayindemo" in joined and "4 sites" in joined
    assert item.category == "linkage"


# ── full pipeline (DB) ───────────────────────────────────────────────

@pytest.fixture()
def ctx(db):
    user = User(email=f"uf-{uuid.uuid4().hex[:8]}@example.org")
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
        value_raw="ayindemo", value_normalized="ayindemo",
    )
    db.add_all([email, username])
    db.flush()
    scan = Scan(requester_user_id=user.id, subject_id=subject.id)
    db.add(scan)
    db.flush()
    db.commit()
    return {"user": user, "subject": subject, "scan": scan, "username": username}


def _uf_finding(db, ctx, *, category=FindingCategory.SOCIAL, confidence=0.85,
                sensitivity=Sensitivity.MEDIUM, payload=None, key=None):
    f = Finding(
        scan_id=ctx["scan"].id, subject_id=ctx["subject"].id,
        identifier_id=ctx["username"].id,
        category=category, sensitivity=sensitivity,
        source="username_footprint", source_name="Username Footprint",
        source_url="https://github.com/ayindemo",
        captured_at=NOW, confidence=confidence,
        summary="Clearly-fake fixture username finding.",
        payload=payload or {},
        dedupe_key=key or f"username_footprint:{uuid.uuid4().hex[:8]}",
    )
    db.add(f)
    db.flush()
    return f


def test_username_finding_capped_possible_then_scores_on_confirm(db, ctx):
    # Even at verified-grade 0.85, a username (not control-verifiable) finding must
    # NOT auto-match — the anti-namesake wall keeps it "possible" until confirmed.
    f = _uf_finding(db, ctx, payload={"site_id": "github", "site": "GitHub",
                                      "opt_out_url": "https://github.com/settings/admin",
                                      "opt_out_instructions": "Delete the account."})
    resolve_scan(db, ctx["scan"])
    db.refresh(f)
    assert f.match_status is MatchStatus.POSSIBLE
    assert f.match_confidence <= 0.65  # the anti-namesake cap

    # possible → does not move the number
    assert compute_score(db, ctx["scan"]).subscores["social"] == 0

    # user confirms it's theirs → it now scores AND gets a concrete removal item
    f.match_status = MatchStatus.CONFIRMED
    db.flush()
    assert compute_score(db, ctx["scan"]).subscores["social"] > 0
    _, items = build_checklist(db, ctx["scan"])
    gh = [it for it in items if "GitHub" in it.title]
    assert gh and any("Delete the account." in s for s in gh[0].steps)


def test_linkage_finding_scores_into_linkage_subscore(db, ctx):
    f = _uf_finding(
        db, ctx, category=FindingCategory.LINKAGE,
        payload={"kind": "handle_linkage", "handle": "ayindemo", "site_count": 4},
        key="username_footprint:linkage:ayindemo",
    )
    resolve_scan(db, ctx["scan"])
    db.refresh(f)
    assert f.match_status is MatchStatus.POSSIBLE  # capped like every username finding

    f.match_status = MatchStatus.CONFIRMED
    db.flush()
    assert compute_score(db, ctx["scan"]).subscores["linkage"] > 0
    _, items = build_checklist(db, ctx["scan"])
    assert any(it.category == "linkage" for it in items)
