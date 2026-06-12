"""B1 acceptance: the grounded report narrative.

- templates alone produce a fully sourced narrative (claims, per-category
  summaries, top fixes) — no LLM required
- a citation-clean LLM draft is served and flagged as such
- an LLM draft citing an invented finding id, or making an unsourced claim,
  is REJECTED by the citation guard and the report falls back to templates
  (CLAUDE.md #5 — the golden path)
- credential details never enter the narrative context (the LLM cannot leak
  what it never saw); the report route serves the narrative without step-up
- the narrative caches on the Score row, regenerates when the score
  recomputes, upgrades from template to LLM when one becomes available, and
  every generation is audited

All data clearly fake.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayin import report
from ayin.api.main import create_app
from ayin.api.routes.auth import get_email_sender
from ayin.api.routes.scans import get_registry, get_vault
from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.llm import MockLLMClient, generate_narrative
from ayin.models import AuditRecord, Score
from ayin.orchestrator import engine
from ayin.report import (
    LOCKED_CREDENTIAL_SUMMARY,
    build_narrative_context,
    get_or_generate_narrative,
)
from ayin.scoring.engine import compute_score
from ayin.vault import NullVault
from tests.test_auth import FAKE_PASSWORD, RecordingSender
from tests.test_orchestrator import _mk_user


@pytest.fixture()
def registry():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    return reg


@pytest.fixture()
def scanned(db, registry):
    """A completed inline scan: fake breach (credential) + broker findings."""
    user = _mk_user(db, with_aux=False)
    scan, result = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=registry,
        vault=NullVault(), inline=True,
    )
    assert result.passed
    score = db.execute(select(Score).where(Score.scan_id == scan.id)).scalar_one()
    return {"user": user, "scan": scan, "score": score}


def _valid_llm_json(ctx) -> str:
    """A citation-clean draft over the real finding ids."""
    ids = [f.finding_id for f in ctx.findings]
    return json.dumps(
        {
            "verdict": "A fixture verdict about data exposure only.",
            "claims": [{"text": "Fixture statement.", "finding_ids": ids}],
            "category_summaries": [
                {"category": ctx.findings[0].category, "text": "Fixture summary.",
                 "finding_ids": [ids[0]]}
            ],
            "top_fixes": [{"text": "Fixture fix.", "finding_ids": [ids[0]]}],
        }
    )


# ── Context construction (what the LLM is allowed to see) ───────────


def test_context_masks_credential_summaries(db, scanned):
    ctx = build_narrative_context(db, scanned["scan"], scanned["score"])
    creds = [v for v in ctx.findings if v.category == "credential"]
    assert creds, "fixture scan should produce a credential finding"
    for v in creds:
        assert v.summary == LOCKED_CREDENTIAL_SUMMARY
    # The breach name must never reach the prompt context (it's step-up data).
    assert "ExampleBreach" not in json.dumps([v.summary for v in ctx.findings])


def test_context_carries_honest_score_deltas(db, scanned):
    ctx = build_narrative_context(db, scanned["scan"], scanned["score"])
    assert ctx.overall == scanned["score"].overall
    assert any(v.expected_score_delta > 0 for v in ctx.findings)


# ── Template path (no LLM) ───────────────────────────────────────────


def test_template_narrative_is_complete_and_grounded(db, scanned):
    ctx = build_narrative_context(db, scanned["scan"], scanned["score"])
    res = generate_narrative(ctx, None)
    assert res.used_llm is False and res.guard is None
    draft = res.draft
    assert draft.verdict == ctx.verdict
    assert len(draft.claims) == len(ctx.findings)
    assert {c.category for c in draft.category_summaries} == {
        v.category for v in ctx.findings
    }
    assert 1 <= len(draft.top_fixes) <= 3
    # citation-clean by construction
    allowed = {v.finding_id for v in ctx.findings}
    from ayin.llm import validate_narrative

    assert validate_narrative(draft, allowed).ok


# ── LLM path + citation guard (the golden tests) ─────────────────────


def test_llm_citation_clean_draft_is_served(db, scanned):
    ctx = build_narrative_context(db, scanned["scan"], scanned["score"])
    client = MockLLMClient(responses=[_valid_llm_json(ctx)])
    res = generate_narrative(ctx, client)
    assert res.used_llm is True
    assert res.guard is not None and res.guard.ok
    assert res.model == "mock-qwen"
    assert res.usage is not None and res.usage.total_tokens > 0
    assert res.draft.verdict.startswith("A fixture verdict")


def test_llm_invented_finding_id_is_rejected(db, scanned):
    """The defamation guard: a claim citing a finding that doesn't exist
    can never reach the report (CLAUDE.md #5)."""
    ctx = build_narrative_context(db, scanned["scan"], scanned["score"])
    invented = json.dumps(
        {
            "verdict": "v",
            "claims": [{"text": "You also appear on a leaked forum.",
                        "finding_ids": ["not-a-real-finding-id"]}],
        }
    )
    res = generate_narrative(ctx, MockLLMClient(responses=[invented]))
    assert res.used_llm is False
    assert res.guard is not None and not res.guard.ok
    assert res.guard.invented_ids == ["not-a-real-finding-id"]
    # what got served is the deterministic template, not the bad draft
    assert res.draft.verdict == ctx.verdict
    assert all(
        set(c.finding_ids) <= {v.finding_id for v in ctx.findings}
        for c in res.draft.claims
    )


def test_llm_unsourced_top_fix_is_rejected(db, scanned):
    """Guard covers category summaries and top fixes, not just claims."""
    ctx = build_narrative_context(db, scanned["scan"], scanned["score"])
    ids = [f.finding_id for f in ctx.findings]
    unsourced = json.dumps(
        {
            "verdict": "v",
            "claims": [{"text": "ok", "finding_ids": ids}],
            "top_fixes": [{"text": "Buy our premium plan.", "finding_ids": []}],
        }
    )
    res = generate_narrative(ctx, MockLLMClient(responses=[unsourced]))
    assert res.used_llm is False
    assert res.guard is not None and len(res.guard.unsourced_claims) == 1


# ── Persistence, cache, and audit (DB wiring) ────────────────────────


def _narrative_events(db, scan_id):
    return db.execute(
        select(AuditRecord).where(
            AuditRecord.scan_id == scan_id,
            AuditRecord.event_type == "scan.narrative_generated",
        )
    ).scalars().all()


def test_finalize_pregenerates_and_audits_narrative(db, scanned):
    """The REPORT pipeline step: scan completion leaves a cached, audited
    narrative on the Score row (template path — LLM disabled in tests)."""
    score = scanned["score"]
    assert score.narrative is not None
    assert score.narrative["verdict"]
    meta = score.narrative_meta
    assert meta["used_llm"] is False
    assert meta["score_computed_at"] == score.computed_at.isoformat()
    events = _narrative_events(db, scanned["scan"].id)
    assert len(events) == 1
    assert events[0].detail["used_llm"] is False
    assert events[0].detail["findings_in_context"] == len(score.narrative["claims"])


def test_cache_serves_without_regenerating(db, scanned):
    narrative, meta = get_or_generate_narrative(
        db, scanned["scan"], scanned["score"], get_settings()
    )
    assert narrative == scanned["score"].narrative
    assert len(_narrative_events(db, scanned["scan"].id)) == 1  # no new event


def test_score_recompute_invalidates_cache(db, scanned):
    compute_score(db, scanned["scan"])  # bumps computed_at
    db.flush()
    get_or_generate_narrative(db, scanned["scan"], scanned["score"], get_settings())
    assert len(_narrative_events(db, scanned["scan"].id)) == 2


def test_template_cache_upgrades_when_llm_appears(db, scanned, monkeypatch):
    ctx = build_narrative_context(db, scanned["scan"], scanned["score"])
    client = MockLLMClient(responses=[_valid_llm_json(ctx)])
    monkeypatch.setattr(report, "get_llm_client", lambda settings=None: client)
    narrative, meta = get_or_generate_narrative(
        db, scanned["scan"], scanned["score"], get_settings()
    )
    assert meta["used_llm"] is True and meta["model"] == "mock-qwen"
    assert meta["usage"]["total_tokens"] > 0
    # …and the LLM-written cache is final: a second call serves it untouched.
    again, meta2 = get_or_generate_narrative(
        db, scanned["scan"], scanned["score"], get_settings()
    )
    assert again == narrative and len(client.calls) == 1


def test_guard_rejection_is_audited(db, scanned, monkeypatch):
    bad = json.dumps(
        {"verdict": "v",
         "claims": [{"text": "invented", "finding_ids": ["ghost-finding"]}]}
    )
    monkeypatch.setattr(
        report, "get_llm_client",
        lambda settings=None: MockLLMClient(responses=[bad]),
    )
    compute_score(db, scanned["scan"])  # invalidate the finalize-time cache
    db.flush()
    _, meta = get_or_generate_narrative(
        db, scanned["scan"], scanned["score"], get_settings()
    )
    assert meta["used_llm"] is False and meta["guard_ok"] is False
    last = _narrative_events(db, scanned["scan"].id)[-1]
    assert last.detail["guard_ok"] is False
    assert last.detail["invented_finding_ids"] == ["ghost-finding"]


# ── Route (API surface) ──────────────────────────────────────────────


@pytest.fixture()
def sender():
    return RecordingSender()


@pytest.fixture()
def client(sender, registry):
    app = create_app(get_settings())
    app.dependency_overrides[get_email_sender] = lambda: sender
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_vault] = lambda: NullVault()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ready_user(client, sender, unique_email):
    client.post("/auth/signup", json={"email": unique_email, "password": FAKE_PASSWORD})
    token = sender.last_link_token()
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    version = client.get("/tos").json()["current_version"]
    assert client.post("/tos/accept", json={"version": version}).status_code == 200
    return unique_email


def test_report_route_serves_grounded_narrative(client, db, ready_user):
    scan_id = client.post("/scans").json()["id"]
    res = client.get(f"/scans/{scan_id}/report")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["overall"] > 0
    nar = body["narrative"]
    assert nar["generated_by"] == "template"  # LLM disabled in tests
    assert nar["verdict"]
    assert nar["claims"] and nar["category_summaries"] and nar["top_fixes"]

    # every cited finding id is a real finding of this scan
    finding_ids = {
        f["id"] for f in client.get(f"/scans/{scan_id}/findings").json()["findings"]
    }
    for section in ("claims", "category_summaries", "top_fixes"):
        for entry in nar[section]:
            assert entry["finding_ids"]
            assert set(entry["finding_ids"]) <= finding_ids

    # no credential detail leaks into the narrative without step-up
    assert "ExampleBreach" not in res.text

    # serving the report wrote a data-access audit record
    access = db.execute(
        select(AuditRecord).where(
            AuditRecord.scan_id == uuid.UUID(scan_id),
            AuditRecord.event_type == "data.access",
            AuditRecord.resource == "report",
        )
    ).scalars().all()
    assert len(access) == 1


def test_report_404_for_unknown_scan(client, ready_user):
    res = client.get(f"/scans/{uuid.uuid4()}/report")
    assert res.status_code == 404
