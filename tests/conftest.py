import os
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import httpx
import pytest
import redis.asyncio as redis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError
from tenacity import wait_none

from app.core import http as http_module
from app.core.config import Settings
from app.core.health import get_cache
from app.main import create_app
from app.services.weather.dependencies import get_weather_service
from app.services.weather.providers.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.services.weather.providers.open_meteo_weather import OpenMeteoWeatherClient
from app.services.weather.service import WeatherService
from tests.doubles import InMemoryCache

# Nothing listens on port 1: tests that build the app from settings must never
# touch the developer's Redis. Integration tests use their own Redis (`redis_client`).
UNREACHABLE_REDIS_URL = "redis://localhost:1/0"


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries happen as in production, only without the pauses between attempts."""
    monkeypatch.setattr(http_module, "RETRY_WAIT", wait_none())


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: tests must not depend on the developer's local .env
    return Settings(_env_file=None, redis_url=UNREACHABLE_REDIS_URL, redis_timeout_seconds=0.2)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    """Outgoing HTTP client used by the API clients; requests are intercepted by respx."""
    async with httpx.AsyncClient() as http_client:
        yield http_client


@pytest.fixture
def cache() -> InMemoryCache:
    return InMemoryCache()


@pytest.fixture
def weather_service(
    settings: Settings, http: httpx.AsyncClient, cache: InMemoryCache
) -> WeatherService:
    """The real service and clients; only the network is mocked (respx)."""
    return WeatherService(
        geocoding=OpenMeteoGeocodingClient(
            http, settings.open_meteo_geocoding_url, settings.open_meteo_place_url
        ),
        weather=OpenMeteoWeatherClient(http, settings.open_meteo_forecast_url),
        cache=cache,
    )


@pytest.fixture
def app(settings: Settings, weather_service: WeatherService, cache: InMemoryCache) -> FastAPI:
    application = create_app(settings)
    # ASGITransport does not run the lifespan, so the service and the cache are provided directly.
    application.dependency_overrides[get_weather_service] = lambda: weather_service
    application.dependency_overrides[get_cache] = lambda: cache
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# For tests that need real infrastructure (`@pytest.mark.integration`). Locally the containers
# come from docker-compose.yml; in CI from GitHub Actions service containers. If the
# infrastructure is not reachable the tests FAIL: a passing run always means the code was
# really tested against Redis.
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")
DEV_REDIS_PORT = 6379


@pytest.fixture
async def redis_client() -> AsyncIterator[redis.Redis]:
    """A client for the test Redis, emptied before and after every test."""
    if urlparse(TEST_REDIS_URL).port == DEV_REDIS_PORT:
        pytest.fail(f"Refusing to flush {TEST_REDIS_URL}: that looks like the dev Redis")

    client = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True, socket_timeout=1)
    error: RedisError | None = None
    try:
        await client.ping()
    except RedisError as exc:
        error = exc
    if error is not None:
        # Outside the except block, so pytest prints only this message, not Redis's traceback.
        await client.aclose()
        pytest.fail(
            f"Test Redis at {TEST_REDIS_URL} is not reachable.\n"
            "Integration tests need the Docker container running:\n"
            "    docker compose up -d redis-test\n"
            "Run only the tests that need no Docker with: poetry run poe test-unit\n"
            f"(Redis error: {error})",
            pytrace=False,
        )

    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
