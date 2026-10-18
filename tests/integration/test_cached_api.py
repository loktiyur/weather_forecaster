"""The whole request path with the real Redis: API → service → RedisCache → Redis."""

from collections.abc import AsyncIterator

import httpx
import pytest
import redis.asyncio as redis
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_weather_service
from app.cache.redis_cache import RedisCache
from app.clients.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.clients.open_meteo_weather import OpenMeteoWeatherClient
from app.config import Settings
from app.main import create_app, lifespan
from app.services.weather_service import WeatherService
from tests.api.upstream import mock_forecast, mock_geocoding
from tests.integration.conftest import TEST_REDIS_URL

pytestmark = pytest.mark.integration

CURRENT = "/api/v1/weather/current"


@pytest.fixture
async def client(
    settings: Settings, http: httpx.AsyncClient, redis_client: redis.Redis
) -> AsyncIterator[AsyncClient]:
    app: FastAPI = create_app(settings)
    service = WeatherService(
        geocoding=OpenMeteoGeocodingClient(http, settings.open_meteo_geocoding_url),
        weather=OpenMeteoWeatherClient(http, settings.open_meteo_forecast_url),
        cache=RedisCache(redis_client),
    )
    app.dependency_overrides[get_weather_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_second_request_comes_from_redis(
    client: AsyncClient, respx_mock: respx.MockRouter, redis_client: redis.Redis
) -> None:
    geocoding = mock_geocoding(respx_mock)
    forecast = mock_forecast(respx_mock, "forecast_current")

    first = await client.get(CURRENT, params={"city": "Prague"})
    second = await client.get(CURRENT, params={"city": "Prague"})

    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["current"] == first.json()["current"]
    assert geocoding.call_count == forecast.call_count == 1

    assert sorted(await redis_client.keys("*")) == [
        "geo:prague:",
        "weather:current:50.09:14.42:metric",
    ]
    assert 0 < await redis_client.ttl("weather:current:50.09:14.42:metric") <= 600


async def test_ready_with_real_redis(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"redis": "ok"}


async def test_lifespan_connects_to_redis(
    settings: Settings,
    redis_client: redis.Redis,
    respx_mock: respx.MockRouter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Real startup with a reachable Redis: no warning, and responses get cached."""
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current")
    app = create_app(settings.model_copy(update={"redis_url": TEST_REDIS_URL}))

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.get(CURRENT, params={"city": "Prague"})
            second = await ac.get(CURRENT, params={"city": "Prague"})

    assert second.json()["cached"] is True
    assert "running without cache" not in caplog.text
