"""Test fixtures.

Tests run against a real, throwaway Postgres (via `pgserver` — no Docker
required) and `fakeredis`. All fixture data is clearly fake; never put real
PII, credentials, or scan data in tests (CLAUDE.md).
"""

import os
import uuid

import fakeredis
import pytest

# ── Test environment must be set before any ayin import ─────────────
_PGDATA = os.environ.get("AYIN_TEST_PGDATA", "/tmp/ayin-test-pg")

import pgserver  # noqa: E402

_pg = pgserver.get_server(_PGDATA)
os.environ["DATABASE_URL"] = _pg.get_uri()
os.environ["APP_ENV"] = "test"
os.environ["EMAIL_CONSOLE_FALLBACK"] = "true"

from alembic import command as alembic_command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from sqlalchemy import text  # noqa: E402

from ayin.config import get_settings  # noqa: E402
from ayin.db import get_engine, get_sessionmaker  # noqa: E402

get_settings.cache_clear()

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def _migrated():
    """Apply migrations once per test session — proves they run on an empty DB."""
    cfg = AlembicConfig(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "migrations"))
    alembic_command.upgrade(cfg, "head")
    yield


@pytest.fixture(scope="session")
def engine(_migrated):
    return get_engine()


@pytest.fixture(autouse=True)
def _clean_db(_migrated):
    """Start every test from an empty (but migrated) database.

    The audit trigger blocks row UPDATE/DELETE (app-level immutability);
    TRUNCATE remains possible for the table *owner* only — tests are the
    owner, the production app role never is. See migration 0001.
    """
    _truncate_all(get_engine())
    yield


@pytest.fixture()
def db(engine):
    with get_sessionmaker()() as session:
        yield session


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeRedis()


@pytest.fixture()
def unique_email() -> str:
    """Clearly-fake, collision-free address for a test user."""
    return f"test-{uuid.uuid4().hex[:10]}@example.org"


def _truncate_all(engine) -> None:
    with engine.begin() as conn:
        tables = (
            conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename != 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            conn.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
        # Re-seed config rows the migrations install (truncate wiped them),
        # so every test starts from the canonical seeded state.
        conn.execute(
            text(
                "INSERT INTO rate_limit_policies "
                "(id, scope, scans_per_day, scan_burst, burst_window_minutes) "
                "VALUES (gen_random_uuid(), 'free', :spd, :burst, 10)"
            ),
            {"spd": get_settings().rate_limit_scans_per_day,
             "burst": get_settings().rate_limit_burst},
        )
