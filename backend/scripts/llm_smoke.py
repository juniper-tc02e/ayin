r"""One-shot LLM smoke test: the full self-scan pipeline against a REAL Qwen
model — local Ollama by default, Qwen Cloud with env overrides. This is the
ADR-0003 "make one real call early" de-risk, and a dry run of the demo flow
(planner decisions visible in the audit log, grounded narrative, guard
verdicts).

Fixture data only (FakeConnector — clearly fake seeds, no real sources, no
real PII). Runs on a throwaway pgserver Postgres, like the test suite.

Default model is qwen2.5:3b (non-thinking): qwen3's thinking mode burns the
token budget invisibly through Ollama's OpenAI-compatible /v1 endpoint
(verified 2026-06-12 — content comes back empty). On Qwen Cloud use a
commercial model or QWEN_EXTRA_BODY='{"enable_thinking": false}'.

Usage (PowerShell, from backend/):
  & "$env:LOCALAPPDATA\ayin-venv\Scripts\python.exe" scripts\llm_smoke.py

  # Against Qwen Cloud instead of local Ollama:
  $env:QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
  $env:QWEN_API_KEY  = "<key>"        # never commit; session env only
  $env:QWEN_MODEL    = "qwen-plus"
  & "$env:LOCALAPPDATA\ayin-venv\Scripts\python.exe" scripts\llm_smoke.py
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

# ── env must be set before any ayin import (mirrors tests/conftest.py) ──
_LOCAL = os.environ.get("LOCALAPPDATA") or "/tmp"  # noqa: S108 — dev-only throwaway pgdata
_PGDATA = os.environ.get("AYIN_TEST_PGDATA", os.path.join(_LOCAL, "ayin-smoke-pg"))

import pgserver  # noqa: E402

_pg = pgserver.get_server(_PGDATA)
os.environ["DATABASE_URL"] = _pg.get_uri()
os.environ["APP_ENV"] = "test"
os.environ["EMAIL_CONSOLE_FALLBACK"] = "true"
os.environ.setdefault("LLM_ENABLED", "true")
os.environ.setdefault("QWEN_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("QWEN_MODEL", "qwen2.5:3b")  # non-thinking (see docstring)
os.environ.setdefault("QWEN_TIMEOUT_SECONDS", "300")  # CPU inference is slow

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)

from alembic import command as alembic_command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from sqlalchemy import select  # noqa: E402

from ayin.config import get_settings  # noqa: E402

get_settings.cache_clear()

cfg = AlembicConfig(os.path.join(_BACKEND, "alembic.ini"))
cfg.set_main_option("script_location", os.path.join(_BACKEND, "migrations"))
alembic_command.upgrade(cfg, "head")

from ayin.connectors import ConnectorRegistry  # noqa: E402
from ayin.connectors.fake import FakeConnector  # noqa: E402
from ayin.db import get_sessionmaker  # noqa: E402
from ayin.models import AuditRecord, Finding, Score, Subject, User  # noqa: E402
from ayin.models.enums import IdentifierKind, VerificationState  # noqa: E402
from ayin.models.subject import Identifier  # noqa: E402
from ayin.orchestrator import engine  # noqa: E402
from ayin.remediation.llm_guidance import ensure_llm_guidance  # noqa: E402
from ayin.vault import NullVault  # noqa: E402

settings = get_settings()
print("== Ayin LLM smoke test ==")
print(f"endpoint: {settings.qwen_base_url}  model: {settings.qwen_model}")
print(f"llm_enabled: {settings.llm_enabled}\n")

reg = ConnectorRegistry()
reg.register(FakeConnector)
reg.enable("fake", environment="test")

NOW = datetime.now(timezone.utc)

with get_sessionmaker()() as db:
    # clearly-fake self-scan subject: verified email anchor + aux username
    user = User(email=f"smoke-{uuid.uuid4().hex[:8]}@example.org")
    db.add(user)
    db.flush()
    subject = Subject(owner_user_id=user.id)
    db.add(subject)
    db.flush()
    db.add(Identifier(
        subject_id=subject.id, kind=IdentifierKind.EMAIL,
        value_raw=user.email, value_normalized=user.email,
        verification_state=VerificationState.VERIFIED, verified_at=NOW,
    ))
    db.add(Identifier(
        subject_id=subject.id, kind=IdentifierKind.USERNAME,
        value_raw="fake_handle", value_normalized="fake_handle",
    ))
    db.commit()

    print(">> running scan (planner + connectors + ER assist + narrative)...")
    scan, gate = engine.start_scan(
        db, requester=user, settings=settings, registry=reg,
        vault=NullVault(), inline=True,
    )
    db.expire_all()
    scan = db.get(type(scan), scan.id)
    print(f"scan: {scan.status.value}  (gate: {gate.decision.value})\n")

    print("== planner audit trail ==")
    events = db.execute(
        select(AuditRecord).where(
            AuditRecord.scan_id == scan.id,
            AuditRecord.event_type.in_([
                "scan.planner_decision", "scan.planner_rejected",
                "scan.planner_done", "scan.planner_fallback",
            ]),
        ).order_by(AuditRecord.id)
    ).scalars().all()
    for e in events:
        print(f"  [{e.event_type}] {json.dumps(e.detail, ensure_ascii=False)}")

    print("\n== grounded narrative ==")
    score = db.execute(select(Score).where(Score.scan_id == scan.id)).scalar_one()
    meta = score.narrative_meta or {}
    print(f"  generated_by: {'qwen' if meta.get('used_llm') else 'template'}"
          f"  model: {meta.get('model')}  guard_ok: {meta.get('guard_ok')}"
          f"  tokens: {(meta.get('usage') or {}).get('total_tokens')}")
    print(json.dumps(score.narrative, indent=2, ensure_ascii=False))

    print("\n== personalized remediation (B3) ==")
    guidance = ensure_llm_guidance(db, scan, settings)
    db.commit()
    print(json.dumps(guidance, indent=2, ensure_ascii=False) if guidance
          else "  (none — playbook only; check scan.remediation_generated audit)")

    print("\n== ER assist opinions (B4, gray zone) ==")
    rows = db.execute(select(Finding).where(Finding.scan_id == scan.id)).scalars().all()
    any_opinion = False
    for f in rows:
        op = (f.resolution or {}).get("llm_opinion")
        if op:
            any_opinion = True
            print(f"  {f.category.value} [{f.match_status.value}] -> "
                  f"{op['verdict']}: {op['evidence']}")
    if not any_opinion:
        print("  (no gray-zone findings annotated)")

    print("\n== guard / generation audit events ==")
    for e in db.execute(
        select(AuditRecord).where(
            AuditRecord.scan_id == scan.id,
            AuditRecord.event_type.in_([
                "scan.narrative_generated", "scan.remediation_generated",
                "scan.er_assist_generated", "scan.narrative_generation_failed",
                "scan.er_assist_generation_failed",
            ]),
        ).order_by(AuditRecord.id)
    ).scalars().all():
        print(f"  [{e.event_type}] {json.dumps(e.detail, ensure_ascii=False)}")

print("\nsmoke test complete.")
