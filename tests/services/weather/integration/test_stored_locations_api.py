"""The whole request path with the real Postgres: API → service → LocationRepository → tables."""

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import Database, get_database
from app.core.health import get_cache
from app.main import create_app
from app.services.weather.dependencies import get_weather_service
from app.services.weather.providers.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.services.weather.providers.open_meteo_weather import OpenMeteoWeatherClient
from app.services.weather.repository import LocationRepository
from app.services.weather.service import WeatherService
from tests.doubles import InMemoryCache
from tests.services.weather.api.upstream import mock_forecast, mock_geocoding, mock_place

pytestmark = pytest.mark.postgres

PLACE = "/api/v1/locations/{}"


@pytest.fixture
async def client(
    settings: Settings, http: httpx.AsyncClient, clean_database: Database
) -> AsyncIterator[AsyncClient]:
    """No cache, so every repeated lookup has to come from the database (or the provider)."""
    app: FastAPI = create_app(settings)
    service = WeatherService(
        geocoding=OpenMeteoGeocodingClient(
            http, settings.open_meteo_geocoding_url, settings.open_meteo_place_url
        ),
        weather=OpenMeteoWeatherClient(http, settings.open_meteo_forecast_url),
        locations=LocationRepository(clean_database.sessions),
    )
    app.dependency_overrides[get_weather_service] = lambda: service
    app.dependency_overrides[get_cache] = InMemoryCache
    app.dependency_overrides[get_database] = lambda: clean_database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_a_place_is_fetched_once_then_served_from_the_database(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    provider = mock_place(respx_mock, "place_kyiv_uk")

    first = await client.get(PLACE.format(703448), params={"lang": "uk"})
    second = await client.get(PLACE.format(703448), params={"lang": "uk"})

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert second.json()["name"] == "Київ"
    assert provider.call_count == 1


async def test_a_place_found_by_name_is_stored(
    client: AsyncClient, respx_mock: respx.MockRouter, clean_database: Database
) -> None:
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current")
    provider = mock_place(respx_mock, "place_kyiv_en")  # must not be called

    weather = await client.get("/api/v1/weather/current", params={"city": "Prague"})
    prague_id = weather.json()["location"]["id"]
    place = await client.get(PLACE.format(prague_id))

    assert place.json() == weather.json()["location"]
    assert provider.call_count == 0
    async with clean_database.engine.connect() as connection:
        names = (
            await connection.execute(
                text("SELECT language, name FROM weather.location_names WHERE location_id = :id"),
                {"id": prague_id},
            )
        ).all()
    assert [tuple(row) for row in names] == [("en", "Prague")]
