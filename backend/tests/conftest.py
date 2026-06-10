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

from sqlalchemy import text  # noqa: E402

from ayin.config import get_settings  # noqa: E402
from ayin.db import get_engine, get_sessionmaker, reset_engine_cache  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session")
def pg_url() -> str:
    return _pg.get_uri()


@pytest.fixture(scope="session")
def engine():
    return get_engine()


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
    return f"test-{uuid.uuid4().hex[:10]}@example.invalid"


def _truncate_all(engine) -> None:
    """Wipe data between tests without dropping schema.

    The audit table's trigger blocks row UPDATE/DELETE (app-level immutability);
    TRUNCATE remains possible for the table *owner* only — which tests are, and
    the production app role never is. See migration 0001.
    """
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename != 'alembic_version'"
            )
        ).scalars().all()
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            conn.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))


__all__ = ["reset_engine_cache", "_truncate_all"]
