from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tenacity import wait_none

from app.api.dependencies import get_weather_service
from app.clients import http as http_module
from app.clients.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.clients.open_meteo_weather import OpenMeteoWeatherClient
from app.config import Settings
from app.main import create_app
from app.services.weather_service import WeatherService
from tests.doubles import InMemoryCache

# Nothing listens on port 1: tests that build the app from settings must never
# touch the developer's Redis. Integration tests use their own Redis (tests/integration).
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
def app(settings: Settings, weather_service: WeatherService) -> FastAPI:
    application = create_app(settings)
    # ASGITransport does not run the lifespan, so the service is provided directly.
    application.dependency_overrides[get_weather_service] = lambda: weather_service
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
