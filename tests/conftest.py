from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_weather_service
from app.clients.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.clients.open_meteo_weather import OpenMeteoWeatherClient
from app.config import Settings
from app.main import create_app
from app.services.weather_service import WeatherService


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: tests must not depend on the developer's local .env
    return Settings(_env_file=None)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    """Outgoing HTTP client used by the API clients; requests are intercepted by respx."""
    async with httpx.AsyncClient() as http_client:
        yield http_client


@pytest.fixture
def weather_service(settings: Settings, http: httpx.AsyncClient) -> WeatherService:
    """The real service and clients; only the network is mocked (respx)."""
    return WeatherService(
        geocoding=OpenMeteoGeocodingClient(http, settings.open_meteo_geocoding_url),
        weather=OpenMeteoWeatherClient(http, settings.open_meteo_forecast_url),
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
