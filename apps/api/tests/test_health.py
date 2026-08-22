"""Health endpoint tests (external dependencies mocked)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


async def _ok() -> bool:
    return True


async def _down() -> bool:
    return False


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.api.routes.health as health_route

    monkeypatch.setattr(health_route, "check_database_connection", _ok)
    monkeypatch.setattr(health_route, "check_redis_connection", _ok)
    return TestClient(create_app())


def test_health_healthy(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["database"] is True
    assert body["redis"] is True
    assert body["version"]


def test_health_degraded_when_redis_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.routes.health as health_route

    monkeypatch.setattr(health_route, "check_redis_connection", _down)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


def test_health_unhealthy_when_all_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.routes.health as health_route

    monkeypatch.setattr(health_route, "check_database_connection", _down)
    monkeypatch.setattr(health_route, "check_redis_connection", _down)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unhealthy"
