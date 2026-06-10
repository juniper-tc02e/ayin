"""Database engine / session plumbing (SQLAlchemy 2.0)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ayin.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency — one session per request."""
    with get_sessionmaker()() as session:
        yield session


def reset_engine_cache() -> None:
    """Test helper: drop cached engine/sessionmaker after settings change."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
