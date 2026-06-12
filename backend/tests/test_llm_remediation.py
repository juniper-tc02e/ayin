"""B3 acceptance: LLM-personalized remediation guidance.

- the playbook is the floor: no LLM → checklist unchanged, no guidance rows
- a citation-clean plan persists as RemediationTask rows (status=SUGGESTED),
  serves as personalized_steps on the checklist, generates exactly once
  (cached), and is audited
- a plan covering an unknown finding id is rejected wholesale (same guard
  as the narrative — CLAUDE.md #5)
- credential items never leak breach detail into the model's context

All data clearly fake.
"""

import json

import pytest
from sqlalchemy import select

from ayin.config import get_settings
from ayin.connectors import ConnectorRegistry
from ayin.connectors.fake import FakeConnector
from ayin.llm import MockLLMClient
from ayin.llm.client import LLMUnavailable
from ayin.llm.remediation import RemediationItemView, generate_remediation
from ayin.models import AuditRecord, RemediationTask
from ayin.models.enums import RemediationStatus, RemediationType
from ayin.orchestrator import engine
from ayin.remediation import build_checklist, llm_guidance
from ayin.remediation.llm_guidance import ensure_llm_guidance
from ayin.vault import NullVault
from tests.test_orchestrator import _mk_user

VIEW = RemediationItemView(
    finding_id="f-1", category="credential", sensitivity="high",
    title="Rotate a password exposed in a breach",
    baseline_steps=["Change the password.", "Turn on MFA."],
)


def _plan(*drafts) -> str:
    return json.dumps({"items": list(drafts)})


# ── Pure generation + guard ──────────────────────────────────────────


def test_no_client_keeps_playbook():
    res = generate_remediation([VIEW], None)
    assert res.steps_by_finding == {} and res.used_llm is False


def test_valid_plan_is_served():
    client = MockLLMClient(
        responses=[_plan({"finding_id": "f-1", "steps": ["Do A.", "Do B."]})]
    )
    res = generate_remediation([VIEW], client)
    assert res.used_llm is True and res.guard.ok
    assert res.steps_by_finding == {"f-1": ["Do A.", "Do B."]}
    assert res.usage.total_tokens > 0


def test_invented_finding_id_rejects_whole_plan():
    client = MockLLMClient(
        responses=[
            _plan(
                {"finding_id": "f-1", "steps": ["fine"]},
                {"finding_id": "ghost-finding", "steps": ["invented"]},
            )
        ]
    )
    res = generate_remediation([VIEW], client)
    assert res.used_llm is False
    assert res.steps_by_finding == {}
    assert res.guard is not None and res.guard.invented_ids == ["ghost-finding"]


def test_llm_failure_keeps_playbook():
    class DownClient(MockLLMClient):
        def complete(self, messages, **kwargs):
            raise LLMUnavailable("fixture: endpoint down")

    res = generate_remediation([VIEW], DownClient())
    assert res.steps_by_finding == {} and res.used_llm is False


# ── Persistence + checklist wiring ───────────────────────────────────


@pytest.fixture()
def scanned(db):
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.enable("fake", environment="test")
    user = _mk_user(db, with_aux=False)
    scan, result = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=reg,
        vault=NullVault(), inline=True,
    )
    assert result.passed
    return {"user": user, "scan": scan}


def _plan_for(db, scan) -> tuple[str, list[str]]:
    _, items = build_checklist(db, scan, elevated=False)
    ids = [i.finding_id for i in items]
    plan = _plan(
        *[{"finding_id": fid, "steps": [f"Personalized step for {fid}."]} for fid in ids]
    )
    return plan, ids


def test_guidance_persists_caches_and_audits(db, scanned, monkeypatch):
    plan, ids = _plan_for(db, scanned["scan"])
    client = MockLLMClient(responses=[plan])
    monkeypatch.setattr(llm_guidance, "get_llm_client", lambda settings=None: client)

    guidance = ensure_llm_guidance(db, scanned["scan"], get_settings())
    assert set(guidance) == set(ids)

    tasks = db.execute(select(RemediationTask)).scalars().all()
    assert len(tasks) == len(ids)
    by_type = {t.type for t in tasks}
    assert RemediationType.OPT_OUT in by_type  # the broker finding
    assert RemediationType.HARDENING in by_type  # the credential finding
    assert all(t.status == RemediationStatus.SUGGESTED for t in tasks)
    assert all(t.evidence["guard_ok"] is True for t in tasks)

    events = db.execute(
        select(AuditRecord).where(
            AuditRecord.event_type == "scan.remediation_generated"
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].detail["items_generated"] == len(ids)

    # second call serves the rows — no new LLM call, no new audit event
    again = ensure_llm_guidance(db, scanned["scan"], get_settings())
    assert again == guidance
    assert len(client.calls) == 1


def test_no_llm_means_no_rows_and_playbook_only(db, scanned):
    guidance = ensure_llm_guidance(db, scanned["scan"], get_settings())
    assert guidance == {}
    assert db.execute(select(RemediationTask)).scalars().all() == []


def test_rejected_plan_writes_no_rows_but_audits(db, scanned, monkeypatch):
    bad = _plan({"finding_id": "ghost-finding", "steps": ["invented"]})
    client = MockLLMClient(responses=[bad])
    monkeypatch.setattr(llm_guidance, "get_llm_client", lambda settings=None: client)
    guidance = ensure_llm_guidance(db, scanned["scan"], get_settings())
    assert guidance == {}
    assert db.execute(select(RemediationTask)).scalars().all() == []
    event = db.execute(
        select(AuditRecord).where(
            AuditRecord.event_type == "scan.remediation_generated"
        )
    ).scalars().one()
    assert event.detail["guard_ok"] is False
    assert event.detail["invented_finding_ids"] == ["ghost-finding"]


def test_model_context_never_sees_breach_detail(db, scanned, monkeypatch):
    plan, _ = _plan_for(db, scanned["scan"])
    client = MockLLMClient(responses=[plan])
    monkeypatch.setattr(llm_guidance, "get_llm_client", lambda settings=None: client)
    ensure_llm_guidance(db, scanned["scan"], get_settings())
    everything = json.dumps([[m.model_dump() for m in c] for c in client.calls], default=str)
    assert "ExampleBreach" not in everything
