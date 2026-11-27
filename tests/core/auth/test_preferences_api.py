"""GET /me preferences and PATCH /me/preferences, against the real test Postgres."""

import asyncio
from typing import Any

import pytest
import respx
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import Database
from app.services.weather.dependencies import get_weather_service
from app.services.weather.service import WeatherService
from tests.core.auth.conftest import ME, PREFERENCES
from tests.services.weather.api.upstream import mock_forecast, mock_geocoding

pytestmark = pytest.mark.postgres

NONE_CHOSEN = {"units": None, "language": None}


async def stored(database: Database) -> dict[str, Any]:
    async with database.engine.connect() as connection:
        value: dict[str, Any] = await connection.scalar(text("SELECT preferences FROM auth.users"))
        return value


async def test_a_new_user_has_chosen_nothing(
    logged_in: AsyncClient, clean_database: Database
) -> None:
    me = await logged_in.get(ME)

    assert me.json()["preferences"] == NONE_CHOSEN
    assert await stored(clean_database) == {}


async def test_only_the_fields_sent_change(
    logged_in: AsyncClient, clean_database: Database
) -> None:
    first = await logged_in.patch(PREFERENCES, json={"units": "imperial"})
    second = await logged_in.patch(PREFERENCES, json={"language": "uk"})

    assert first.json() == {"units": "imperial", "language": None}
    assert second.json() == {"units": "imperial", "language": "uk"}
    assert (await logged_in.get(ME)).json()["preferences"] == second.json()
    assert await stored(clean_database) == {"units": "imperial", "language": "uk"}


async def test_null_removes_a_choice(logged_in: AsyncClient, clean_database: Database) -> None:
    await logged_in.patch(PREFERENCES, json={"units": "imperial", "language": "cs"})

    response = await logged_in.patch(PREFERENCES, json={"units": None})

    assert response.json() == {"units": None, "language": "cs"}
    assert await stored(clean_database) == {"language": "cs"}  # nothing stored for units


async def test_parallel_changes_of_different_fields_both_survive(
    logged_in: AsyncClient, clean_database: Database
) -> None:
    # One UPDATE each, merged inside Postgres: no change is overwritten by a stale copy.
    await asyncio.gather(
        *(logged_in.patch(PREFERENCES, json={"units": "imperial"}) for _ in range(5)),
        *(logged_in.patch(PREFERENCES, json={"language": "ru"}) for _ in range(5)),
    )

    assert await stored(clean_database) == {"units": "imperial", "language": "ru"}


async def test_an_empty_body_changes_nothing(logged_in: AsyncClient) -> None:
    await logged_in.patch(PREFERENCES, json={"units": "imperial"})

    response = await logged_in.patch(PREFERENCES, json={})

    assert response.json() == {"units": "imperial", "language": None}


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"units": "kelvin"}, "units"),
        ({"language": "de"}, "language"),
        ({"theme": "dark"}, "theme"),
    ],
)
async def test_invalid_preferences_are_422(
    logged_in: AsyncClient, body: dict[str, str], field: str
) -> None:
    response = await logged_in.patch(PREFERENCES, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field


async def test_guests_cannot_change_preferences(client: AsyncClient) -> None:
    response = await client.patch(PREFERENCES, json={"units": "imperial"})

    assert response.status_code == 401


# --- weather in the saved units -----------------------------------------------------------

CURRENT = "/api/v1/weather/current"


@pytest.fixture
def weather(app: FastAPI, weather_service: WeatherService) -> None:
    """The real weather service on mocked upstreams (respx), in the auth test app."""
    app.dependency_overrides[get_weather_service] = lambda: weather_service


@pytest.mark.parametrize(
    ("saved", "requested", "expected"),
    [
        (None, None, "°C"),  # never chose: the default
        ("imperial", None, "°F"),  # chose imperial
        ("imperial", "metric", "°C"),  # `units` in the URL wins
    ],
)
async def test_weather_uses_the_saved_units(
    logged_in: AsyncClient,
    respx_mock: respx.MockRouter,
    saved: str | None,
    requested: str | None,
    expected: str,
    weather: None,
) -> None:
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current")
    if saved:
        await logged_in.patch(PREFERENCES, json={"units": saved})
    params = {"city": "Prague"} | ({"units": requested} if requested else {})

    response = await logged_in.get(CURRENT, params=params)

    assert response.status_code == 200
    assert response.json()["units"]["temperature"] == expected
    visibility = "public" if requested else "private"
    assert response.headers["cache-control"].startswith(f"{visibility},")
