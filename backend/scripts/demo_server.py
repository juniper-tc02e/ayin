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

from ayin.config import get_settings  # noqa: E402

get_settings.cache_clear()

cfg = AlembicConfig(os.path.join(_BACKEND, "alembic.ini"))
cfg.set_main_option("script_location", os.path.join(_BACKEND, "migrations"))
alembic_command.upgrade(cfg, "head")

import uvicorn  # noqa: E402

from ayin.api.main import create_app  # noqa: E402
from ayin.api.routes.scans import get_registry, get_vault  # noqa: E402
from ayin.connectors import ConnectorRegistry  # noqa: E402
from ayin.connectors.fake import FakeConnector  # noqa: E402
from ayin.db import get_sessionmaker  # noqa: E402
from ayin.demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_account  # noqa: E402
from ayin.vault import NullVault  # noqa: E402

settings = get_settings()

with get_sessionmaker()() as db:
    # Same idempotent, self-healing seed the deployed stack uses (ayin.demo) —
    # one definition of "the demo account" across dev and prod.
    created = seed_demo_account(db, settings)
    db.commit()
    print(f"demo account {'seeded' if created else 'already present'}: {DEMO_EMAIL}")

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
