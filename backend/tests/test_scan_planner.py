"""B2 acceptance: the Qwen scan planner (agentic dispatch).

- connector tool specs are non-sensitive projections of the contract
- the planner parses tool calls into PlannerDecisions and feeds results back
- the orchestrator executes ONLY proposals inside the pre-gated job set;
  anything else is refused and audited (the LLM proposes, never bypasses —
  CLAUDE.md #7)
- every accepted decision lands in the audit log with the model's reasoning
- the planner never sees identifier values (minimization)
- planner failure of any kind degrades to deterministic dispatch — the scan
  always completes

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
from ayin.llm.planner import (
    MAX_INVALID_PROPOSALS,
    ConnectorTool,
    ScanPlanner,
    tool_name_for,
)
from ayin.models import AuditRecord, ConnectorJob, Scan
from ayin.models.enums import JobStatus, ScanStatus
from ayin.orchestrator import engine
from ayin.vault import NullVault
from tests.test_orchestrator import SecondConnector, _mk_user


def _tc(name: str, reasoning: str = "fixture reasoning", call_id: str = "call-1") -> dict:
    """One mock tool-calling turn."""
    return {
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps({"reasoning": reasoning})},
            }
        ],
    }


@pytest.fixture()
def registry():
    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.register(SecondConnector)
    reg.enable("fake", environment="test")
    reg.enable("second", environment="test")
    return reg


def _events(db, scan_id, event_type):
    return db.execute(
        select(AuditRecord)
        .where(AuditRecord.scan_id == scan_id, AuditRecord.event_type == event_type)
        .order_by(AuditRecord.id)
    ).scalars().all()


# ── Pure planner protocol ────────────────────────────────────────────


def test_tool_names_are_sanitized():
    assert tool_name_for("fake") == "run_fake"
    assert tool_name_for("breach.hibp") == "run_breach_hibp"


def test_connector_tool_is_a_nonsensitive_projection():
    tool = ConnectorTool.from_connector(FakeConnector)
    spec = tool.as_tool()
    assert spec["function"]["name"] == "run_fake"
    assert "email" in spec["function"]["description"]
    assert "synthetic" in spec["function"]["description"]
    assert spec["function"]["parameters"]["required"] == ["reasoning"]


def test_planner_proposes_observes_and_finishes():
    tools = [ConnectorTool.from_connector(c) for c in (FakeConnector, SecondConnector)]
    client = MockLLMClient(
        responses=[
            _tc("run_second", "social baseline first"),
            _tc("run_fake", "breach check next", call_id="call-2"),
            "all sources have run",
        ]
    )
    p = ScanPlanner(client, tools, seed_kinds=["email"])
    d1 = p.propose()
    assert d1 is not None and d1.connector_id == "second"
    assert d1.reasoning == "social baseline first"
    p.observe({"connector": "second", "status": "done", "findings_by_category": {}})
    d2 = p.propose()
    assert d2 is not None and d2.connector_id == "fake"
    p.observe({"connector": "fake", "status": "done",
               "findings_by_category": {"credential": 1}})
    assert p.propose() is None
    # the model saw the full conversation: system, state, 2×(assistant+tool)
    assert len(client.calls[2]) == 6
    roles = [m.role.value for m in client.calls[2]]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "tool"]


def test_unknown_tool_is_a_strike_then_recovers():
    tools = [ConnectorTool.from_connector(FakeConnector)]
    client = MockLLMClient(responses=[_tc("run_made_up_source"), _tc("run_fake")])
    p = ScanPlanner(client, tools, seed_kinds=["email"])
    d = p.propose()
    assert d is not None and d.connector_id == "fake"
    assert p.invalid_proposals == 1


def test_planner_gives_up_after_strike_budget():
    tools = [ConnectorTool.from_connector(FakeConnector)]
    client = MockLLMClient(
        responses=[_tc("run_made_up_source")] * MAX_INVALID_PROPOSALS
    )
    p = ScanPlanner(client, tools, seed_kinds=["email"])
    assert p.propose() is None
    assert p.exhausted


def test_connector_tool_enumerates_capability_without_instantiation():
    # S1-1 acceptance: the planner reads the class-level manifest and never
    # constructs a connector to learn what it can do.
    from ayin.connectors.broker.detector import BrokerDetectionConnector

    tool = ConnectorTool.from_connector(BrokerDetectionConnector)
    assert tool.output_categories == ["broker"]
    assert tool.latency_class == "slow"
    assert tool.context_used == ["city"]
    desc = tool.as_tool()["function"]["description"]
    assert "broker" in desc.lower()
    assert "slow" in desc.lower()
    assert "city" in desc.lower()


# ── Orchestrator integration (the trust model) ───────────────────────


def test_planned_scan_runs_in_proposed_order_and_audits(db, registry, monkeypatch):
    client = MockLLMClient(
        responses=[
            _tc("run_second", "Baseline the public/social surface first."),
            _tc("run_fake", "A verified email is present — check breach exposure now.",
                call_id="call-2"),
            "done",
        ]
    )
    monkeypatch.setattr("ayin.llm.get_llm_client", lambda settings=None: client)
    user = _mk_user(db)
    scan, result = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=registry,
        vault=NullVault(), inline=True,
    )
    assert result.passed
    db.expire_all()
    assert db.get(Scan, scan.id).status == ScanStatus.DONE

    decisions = _events(db, scan.id, "scan.planner_decision")
    assert [d.detail["connector"] for d in decisions] == ["second", "fake"]
    assert all(d.detail["reasoning"] for d in decisions)
    assert all(d.detail["model"] == "mock-qwen" for d in decisions)
    assert not _events(db, scan.id, "scan.planner_rejected")
    assert not _events(db, scan.id, "scan.planner_fallback")
    done = _events(db, scan.id, "scan.planner_done")
    assert len(done) == 1
    assert done[0].detail["reason"] == "complete"
    assert done[0].detail["connectors_remaining"] == []

    # the proposed order is the executed order
    jobs = {
        j.connector_id: j
        for j in db.execute(
            select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)
        ).scalars()
    }
    assert jobs["second"].status == JobStatus.DONE
    assert jobs["fake"].status == JobStatus.DONE
    assert jobs["second"].started_at < jobs["fake"].started_at


def test_planner_never_sees_identifier_values(db, registry, monkeypatch):
    """Minimization: the planner gets kinds and connector ids — never the
    email address (or any seed value) being scanned."""
    client = MockLLMClient(responses=[_tc("run_fake"), _tc("run_second"), "done"])
    monkeypatch.setattr("ayin.llm.get_llm_client", lambda settings=None: client)
    user = _mk_user(db)
    engine.start_scan(
        db, requester=user, settings=get_settings(), registry=registry,
        vault=NullVault(), inline=True,
    )
    everything_the_model_saw = json.dumps(
        [[m.model_dump() for m in call] for call in client.calls], default=str
    )
    assert user.email not in everything_the_model_saw
    assert "fake_handle" not in everything_the_model_saw  # the aux username


def test_out_of_scope_proposal_is_refused_and_audited(db, registry, monkeypatch):
    """The LLM proposes, never bypasses: re-proposing an already-run job is
    refused by code, audited, and never executed twice."""
    client = MockLLMClient(
        responses=[
            _tc("run_fake", "breach first"),
            _tc("run_fake", "let's run it again", call_id="call-2"),
            _tc("run_second", "ok, the remaining source", call_id="call-3"),
            "done",
        ]
    )
    monkeypatch.setattr("ayin.llm.get_llm_client", lambda settings=None: client)
    user = _mk_user(db)
    scan, _ = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=registry,
        vault=NullVault(), inline=True,
    )
    rejected = _events(db, scan.id, "scan.planner_rejected")
    assert len(rejected) == 1
    assert rejected[0].detail["connector"] == "fake"
    assert "pre-gated" in rejected[0].detail["reason"]
    # the fake job ran exactly once
    job = db.execute(
        select(ConnectorJob).where(
            ConnectorJob.scan_id == scan.id, ConnectorJob.connector_id == "fake"
        )
    ).scalar_one()
    assert job.attempts == 1
    db.expire_all()
    assert db.get(Scan, scan.id).status == ScanStatus.DONE


def test_planner_exhaustion_is_audited_and_swept(db, registry, monkeypatch):
    """A planner that burns its strike budget re-proposing an already-run
    connector is stopped, the giving-up is AUDITED (not silent), and the
    deterministic sweep still completes the scan."""
    client = MockLLMClient(
        responses=[
            _tc("run_fake", "breach first"),
            _tc("run_fake", "again", call_id="call-2"),
            _tc("run_fake", "again", call_id="call-3"),
            _tc("run_fake", "again", call_id="call-4"),
        ]
    )
    monkeypatch.setattr("ayin.llm.get_llm_client", lambda settings=None: client)
    user = _mk_user(db)
    scan, _ = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=registry,
        vault=NullVault(), inline=True,
    )
    done = _events(db, scan.id, "scan.planner_done")
    assert len(done) == 1
    assert done[0].detail["reason"] == "exhausted"
    assert done[0].detail["connectors_remaining"] == ["second"]
    assert done[0].detail["invalid_proposals"] == MAX_INVALID_PROPOSALS
    # coverage is a product guarantee: the sweep ran what the planner didn't
    db.expire_all()
    assert db.get(Scan, scan.id).status == ScanStatus.DONE
    jobs = db.execute(
        select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)
    ).scalars().all()
    assert all(j.status == JobStatus.DONE for j in jobs)


def test_retryable_failure_keeps_connector_proposable(db, monkeypatch):
    """A transiently-failing job goes back to QUEUED and stays in the
    pre-gated pending set — the planner may legitimately re-propose it."""
    from tests.test_orchestrator import FlakyConnector

    reg = ConnectorRegistry()
    reg.register(FakeConnector)
    reg.register(FlakyConnector)
    reg.enable("fake", environment="test")
    reg.enable("flaky", environment="test")
    # 5 blips: the first job run exhausts run()'s 3 internal retries and
    # fails at the JOB level (back to QUEUED); the re-proposed run succeeds.
    FlakyConnector.fail_budget["n"] = 5

    client = MockLLMClient(
        responses=[
            _tc("run_flaky", "try the flaky source"),
            _tc("run_flaky", "it blipped — retry it", call_id="call-2"),
            _tc("run_fake", "now the breach check", call_id="call-3"),
            "done",
        ]
    )
    monkeypatch.setattr("ayin.llm.get_llm_client", lambda settings=None: client)
    user = _mk_user(db)
    scan, _ = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=reg,
        vault=NullVault(), inline=True,
    )
    # the retry was a legitimate proposal, not a refused one
    assert not _events(db, scan.id, "scan.planner_rejected")
    decisions = _events(db, scan.id, "scan.planner_decision")
    assert [d.detail["connector"] for d in decisions] == ["flaky", "flaky", "fake"]
    db.expire_all()
    assert db.get(Scan, scan.id).status == ScanStatus.DONE
    flaky_job = db.execute(
        select(ConnectorJob).where(
            ConnectorJob.scan_id == scan.id, ConnectorJob.connector_id == "flaky"
        )
    ).scalar_one()
    assert flaky_job.status == JobStatus.DONE
    assert flaky_job.attempts == 2


def test_planner_failure_degrades_to_deterministic_dispatch(db, registry, monkeypatch):
    class DownClient(MockLLMClient):
        def complete(self, messages, **kwargs):
            raise LLMUnavailable("fixture: endpoint down")

    monkeypatch.setattr("ayin.llm.get_llm_client", lambda settings=None: DownClient())
    user = _mk_user(db)
    scan, _ = engine.start_scan(
        db, requester=user, settings=get_settings(), registry=registry,
        vault=NullVault(), inline=True,
    )
    db.expire_all()
    assert db.get(Scan, scan.id).status == ScanStatus.DONE  # scan completed anyway
    fallback = _events(db, scan.id, "scan.planner_fallback")
    assert len(fallback) == 1
    assert "LLMUnavailable" in fallback[0].detail["reason"]
    jobs = db.execute(
        select(ConnectorJob).where(ConnectorJob.scan_id == scan.id)
    ).scalars().all()
    assert all(j.status == JobStatus.DONE for j in jobs)
