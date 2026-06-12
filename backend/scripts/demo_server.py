r"""Local demo/dev server: the REAL API on a throwaway pgserver Postgres with
a pre-seeded demo account — so the frontend (`npm run dev`) can exercise the
full self-scan flow without Docker. Sibling of llm_smoke.py; same bootstrap.

Fixture data only (FakeConnector — clearly fake seeds, no real sources, no
real PII). The demo password below is a committed fixture for a throwaway
local database, not a secret.

Usage (PowerShell):
  # terminal 1 — API on :8000
  cd backend; & "$env:LOCALAPPDATA\ayin-venv\Scripts\python.exe" scripts\demo_server.py
  # terminal 2 — UI on :3000
  cd frontend; npm run dev

LLM: local Ollama by default (qwen2.5:3b — see llm_smoke.py on why not
qwen3); set QWEN_BASE_URL / QWEN_API_KEY / QWEN_MODEL for Qwen Cloud.
Everything degrades to deterministic templates if the endpoint is down.
"""

import os
import sys
from datetime import datetime, timezone

# ── env must be set before any ayin import (mirrors tests/conftest.py) ──
_LOCAL = os.environ.get("LOCALAPPDATA") or "/tmp"  # noqa: S108 — dev-only throwaway pgdata
_PGDATA = os.environ.get("AYIN_DEMO_PGDATA", os.path.join(_LOCAL, "ayin-demo-pg"))

import pgserver  # noqa: E402

_pg = pgserver.get_server(_PGDATA)
os.environ["DATABASE_URL"] = _pg.get_uri()
os.environ["APP_ENV"] = "test"
os.environ["EMAIL_CONSOLE_FALLBACK"] = "true"
os.environ.setdefault("LLM_ENABLED", "true")
os.environ.setdefault("QWEN_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("QWEN_MODEL", "qwen2.5:3b")
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

import uvicorn  # noqa: E402

from ayin.api.main import create_app  # noqa: E402
from ayin.api.routes.scans import get_registry, get_vault  # noqa: E402
from ayin.auth.passwords import hash_password  # noqa: E402
from ayin.connectors import ConnectorRegistry  # noqa: E402
from ayin.connectors.fake import FakeConnector  # noqa: E402
from ayin.db import get_sessionmaker  # noqa: E402
from ayin.models import Subject, TosAcceptance, User  # noqa: E402
from ayin.models.enums import IdentifierKind, VerificationState  # noqa: E402
from ayin.models.subject import Identifier  # noqa: E402
from ayin.vault import NullVault  # noqa: E402

DEMO_EMAIL = "demo-ayin@example.org"
DEMO_PASSWORD = "ayin-demo-password-1"  # noqa: S105 — fixture for a throwaway local DB

settings = get_settings()
NOW = datetime.now(timezone.utc)

with get_sessionmaker()() as db:
    # Idempotent, self-healing seed: every boot re-asserts the demo account's
    # invariants (verified email anchor, aux username, current-ToS acceptance)
    # so a stray "Remove" click during UI work never strands the harness.
    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            email_verified_at=NOW,
        )
        db.add(user)
        db.flush()
        db.add(Subject(owner_user_id=user.id))
        db.flush()
        print(f"seeded demo account: {DEMO_EMAIL}")
    else:
        print(f"demo account already present: {DEMO_EMAIL}")

    subject = db.execute(
        select(Subject).where(Subject.owner_user_id == user.id)
    ).scalar_one()
    identifiers = db.execute(
        select(Identifier).where(Identifier.subject_id == subject.id)
    ).scalars().all()
    by_kind = {(i.kind, i.value_normalized) for i in identifiers}
    if (IdentifierKind.EMAIL, DEMO_EMAIL) not in by_kind:
        # clearly-fake self-scan anchor (gate requires a verified email/phone)
        db.add(Identifier(
            subject_id=subject.id, kind=IdentifierKind.EMAIL,
            value_raw=DEMO_EMAIL, value_normalized=DEMO_EMAIL,
            verification_state=VerificationState.VERIFIED, verified_at=NOW,
        ))
        print("re-seeded verified email anchor")
    if (IdentifierKind.USERNAME, "fake_handle") not in by_kind:
        # aux username — gray-zone "possible match" material for the demo
        db.add(Identifier(
            subject_id=subject.id, kind=IdentifierKind.USERNAME,
            value_raw="fake_handle", value_normalized="fake_handle",
        ))
        print("re-seeded aux username")
    accepted = db.execute(
        select(TosAcceptance.id).where(
            TosAcceptance.user_id == user.id,
            TosAcceptance.version == settings.tos_current_version,
        )
    ).scalar_one_or_none()
    if accepted is None:
        db.add(TosAcceptance(user_id=user.id, version=settings.tos_current_version))
    db.commit()

reg = ConnectorRegistry()
reg.register(FakeConnector)
reg.enable("fake", environment="test")

app = create_app(settings)
app.dependency_overrides[get_registry] = lambda: reg
app.dependency_overrides[get_vault] = lambda: NullVault()

print(f"login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
print(
    f"LLM: enabled={settings.llm_enabled}  endpoint={settings.qwen_base_url}  "
    f"model={settings.qwen_model}"
)
uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
