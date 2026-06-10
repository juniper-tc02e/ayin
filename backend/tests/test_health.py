"""M0-1 acceptance: API boots and the health check reports component status."""

from fastapi.testclient import TestClient

from ayin.api.main import create_app
from ayin.config import get_settings


def test_health_reports_db_ok():
    app = create_app(get_settings())
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["db"] == "ok"  # real (throwaway) Postgres from conftest
    assert body["redis"] in {"ok", "down"}  # no redis in CI sandbox → degraded is fine
    assert body["status"] in {"ok", "degraded"}
    assert body["version"]


def test_health_degrades_not_crashes_without_redis():
    app = create_app(get_settings())
    client = TestClient(app)
    body = client.get("/health").json()
    if body["redis"] == "down":
        assert body["status"] == "degraded"
