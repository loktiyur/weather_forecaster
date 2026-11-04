from fastapi import FastAPI
from httpx import AsyncClient

from app.core.db import get_database
from app.core.health import get_cache
from tests.doubles import StubDatabase, UnavailableCache


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_when_everything_is_reachable(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"redis": "ok", "postgres": "ok"}}


async def test_not_ready_when_cache_is_down(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_cache] = UnavailableCache

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"redis": "unavailable", "postgres": "ok"},
    }


async def test_not_ready_when_database_is_down(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_database] = lambda: StubDatabase(reachable=False)

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"redis": "ok", "postgres": "unavailable"},
    }
