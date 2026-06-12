"""B4 acceptance: gray-zone entity-resolution assist.

- only POSSIBLE findings above the floor confidence are offered to the model
- a guarded judgment lands in resolution["llm_opinion"] and is audited
- THE INVARIANT (FR-ER-1): the opinion never moves match_status or
  match_confidence — even a confident "match" verdict changes nothing;
  only the user's confirm/reject promotes a finding
- judgments citing unknown finding ids are rejected wholesale
- credential summaries never reach the model; annotation is idempotent

All data clearly fake.
"""

import json

import pytest
from sqlalchemy import select

from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.llm import MockLLMClient
from ayin.llm.er_assist import ERCandidateView, judge_gray_zone
from ayin.llm.schemas import ERVerdict
from ayin.models import AuditRecord, Finding
from ayin.models.enums import MatchStatus
from ayin.orchestrator import engine
from ayin.resolution import llm_assist
from ayin.resolution.llm_assist import annotate_gray_zone
from ayin.vault import NullVault
from tests.test_orchestrator import _mk_user

CANDIDATE = ERCandidateView(
    finding_id="f-1", category="social", sensitivity="low",
    source_name="Fake Source", summary="(FAKE) public profile",
    match_confidence=0.65,
    match_reasons=["capped at 0.65 (seed not control-verifiable)"],
)


def _judgments(*items) -> str:
    return json.dumps({"items": list(items)})


# ── Pure judging + guard ─────────────────────────────────────────────


def test_no_client_or_candidates_means_no_opinions():
    assert judge_gray_zone([CANDIDATE], None).judgments_by_finding == {}
    assert judge_gray_zone([], MockLLMClient()).judgments_by_finding == {}


def test_valid_judgment_is_returned():
    client = MockLLMClient(
        responses=[
            _judgments(
                {"finding_id": "f-1", "verdict": "unsure",
                 "evidence": ["single source; username only"]}
            )
        ]
    )
    res = judge_gray_zone([CANDIDATE], client)
    assert res.used_llm is True and res.guard.ok
    assert res.judgments_by_finding["f-1"].verdict == ERVerdict.UNSURE
    assert res.judgments_by_finding["f-1"].evidence


def test_invented_finding_id_rejects_all_judgments():
    client = MockLLMClient(
        responses=[
            _judgments(
                {"finding_id": "f-1", "verdict": "match", "evidence": ["ok"]},
                {"finding_id": "ghost", "verdict": "match", "evidence": ["bad"]},
            )
        ]
    )
    res = judge_gray_zone([CANDIDATE], client)
    assert res.judgments_by_finding == {}
    assert res.guard is not None and res.guard.invented_ids == ["ghost"]


# ── DB annotation + the FR-ER-1 invariant ────────────────────────────


@pytest.fixture()
def scanned(db):
    """Inline scan with an aux username seed → one POSSIBLE social finding
    (capped by the anti-namesake wall) plus auto-matched email findings."""
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    user = _mk_user(db, with_aux=True)
    scan, result = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=reg,
        vault=NullVault(), inline=True,
    )
    assert result.passed
    possible = db.execute(
        select(Finding).where(
            Finding.scan_id == scan.id, Finding.match_status == MatchStatus.POSSIBLE
        )
    ).scalars().all()
    assert len(possible) == 1  # the username profile finding
    return {"scan": scan, "possible": possible[0]}


class _JudgeEverythingClient(MockLLMClient):
    """Reads the candidates out of the prompt and judges each one — lets
    integration tests run without knowing finding ids in advance."""

    def __init__(self, verdict="match"):
        super().__init__()
        self._verdict = verdict

    def complete(self, messages, **kwargs):
        from ayin.llm.schemas import LLMResponse, LLMUsage  # noqa: PLC0415

        self.calls.append(list(messages))
        candidates = json.loads(messages[-1].content)["candidates"]
        items = [
            {"finding_id": c["finding_id"], "verdict": self._verdict,
             "evidence": [f"judged from: {c['rules_match_reasons'][:1]}"]}
            for c in candidates
        ]
        return LLMResponse(
            content=json.dumps({"items": items}), model=self.model,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )


def test_opinion_lands_without_moving_the_match_decision(db, scanned, monkeypatch):
    client = _JudgeEverythingClient(verdict="match")
    monkeypatch.setattr(llm_assist, "get_llm_client", lambda settings=None: client)
    finding = scanned["possible"]
    status_before = finding.match_status
    confidence_before = finding.match_confidence

    verdicts = annotate_gray_zone(db, scanned["scan"], get_settings())
    assert verdicts == {str(finding.id): "match"}

    db.refresh(finding)
    opinion = finding.resolution["llm_opinion"]
    assert opinion["verdict"] == "match" and opinion["evidence"]
    assert opinion["model"] == "mock-qwen"
    # THE INVARIANT: a confident LLM "match" changes nothing (FR-ER-1).
    assert finding.match_status == status_before == MatchStatus.POSSIBLE
    assert finding.match_confidence == confidence_before

    events = db.execute(
        select(AuditRecord).where(
            AuditRecord.event_type == "scan.er_assist_generated"
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].detail["judgments"] == 1
    assert events[0].detail["verdict_counts"] == {"match": 1}


def test_annotation_is_idempotent(db, scanned, monkeypatch):
    client = _JudgeEverythingClient()
    monkeypatch.setattr(llm_assist, "get_llm_client", lambda settings=None: client)
    annotate_gray_zone(db, scanned["scan"], get_settings())
    assert annotate_gray_zone(db, scanned["scan"], get_settings()) == {}
    assert len(client.calls) == 1  # opinion already stored — no second call


def test_auto_matched_findings_are_never_offered(db, scanned, monkeypatch):
    client = _JudgeEverythingClient()
    monkeypatch.setattr(llm_assist, "get_llm_client", lambda settings=None: client)
    annotate_gray_zone(db, scanned["scan"], get_settings())
    offered = json.loads(client.calls[0][-1].content)["candidates"]
    assert [c["finding_id"] for c in offered] == [str(scanned["possible"].id)]
    # credential summaries (auto-matched here anyway) can thus never leak
    assert "ExampleBreach" not in json.dumps(offered)


def test_no_llm_leaves_findings_untouched(db, scanned):
    assert annotate_gray_zone(db, scanned["scan"], get_settings()) == {}
    db.refresh(scanned["possible"])
    assert "llm_opinion" not in (scanned["possible"].resolution or {})
