"""Ayin API gateway — FastAPI app factory.

Routes are added per BUILD-PLAN ticket; this module owns app construction,
CORS, and the health endpoint (M0-1).
"""

import logging

import redis as redis_lib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from ayin import __version__
from ayin.config import Settings, get_settings
from ayin.db import get_engine

log = logging.getLogger("ayin")


def _db_status() -> str:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # pragma: no cover - depends on env
        log.warning("health: database unreachable: %s", exc)
        return "down"


def _redis_status(settings: Settings) -> str:
    try:
        client = redis_lib.Redis.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        client.ping()
        return "ok"
    except Exception as exc:  # pragma: no cover - depends on env
        log.warning("health: redis unreachable: %s", exc)
        return "down"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.assert_production_safe()

    app = FastAPI(
        title="Ayin API",
        version=__version__,
        description="OSINT self-exposure scanner — T0 self-scan only.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        db = _db_status()
        redis_state = _redis_status(settings)
        status = "ok" if db == "ok" and redis_state == "ok" else "degraded"
        return {"status": status, "db": db, "redis": redis_state, "version": __version__}

    from ayin.api.routes import auth, exclusions, findings, identifiers, scans, tos
    from ayin.connectors.bootstrap import configure_default_connectors

    configure_default_connectors(settings)
    app.include_router(auth.router)
    app.include_router(identifiers.router)
    app.include_router(tos.router)
    app.include_router(scans.router)
    app.include_router(findings.router)
    app.include_router(exclusions.router)
    return app


app = create_app()
