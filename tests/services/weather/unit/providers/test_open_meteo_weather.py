import datetime as dt

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError
from app.services.weather.providers.open_meteo_weather import (
    CURRENT_VARIABLES,
    DAILY_VARIABLES,
    OpenMeteoWeatherClient,
)
from app.services.weather.schemas import Units
from tests.fixtures import load_fixture

URL = Settings.model_fields["open_meteo_forecast_url"].default
PRAGUE = (50.08804, 14.42076)


@pytest.fixture
def weather(http: httpx.AsyncClient) -> OpenMeteoWeatherClient:
    return OpenMeteoWeatherClient(http, URL)


async def test_get_current_maps_response(
    weather: OpenMeteoWeatherClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("forecast_current"))
    )

    current = await weather.get_current(*PRAGUE)

    assert current.time == dt.datetime(2026, 10, 16, 14, 15)
    assert current.temperature == 16.0
    assert current.apparent_temperature == 15.2
    assert current.relative_humidity == 60
    assert current.wind_speed == 2.6
    assert current.weather_code == 0
    assert current.description == "Clear sky"
    assert current.is_day is True


async def test_get_current_sends_expected_params(
    weather: OpenMeteoWeatherClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("forecast_current"))
    )

    await weather.get_current(*PRAGUE)

    params = route.calls.last.request.url.params
    assert params["latitude"] == "50.08804"
    assert params["longitude"] == "14.42076"
    assert params["timezone"] == "auto"
    assert params["current"].split(",") == CURRENT_VARIABLES
    assert "temperature_unit" not in params
    assert "wind_speed_unit" not in params


async def test_imperial_units_request_fahrenheit_and_mph(
    weather: OpenMeteoWeatherClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("forecast_current"))
    )

    await weather.get_current(*PRAGUE, units=Units.IMPERIAL)

    params = route.calls.last.request.url.params
    assert params["temperature_unit"] == "fahrenheit"
    assert params["wind_speed_unit"] == "mph"


async def test_get_current_missing_block_raises_upstream_error(
    weather: OpenMeteoWeatherClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json={"latitude": 50.0}))

    with pytest.raises(UpstreamServiceError, match="'current'"):
        await weather.get_current(*PRAGUE)


async def test_get_daily_forecast_turns_columns_into_rows(
    weather: OpenMeteoWeatherClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("forecast_daily"))
    )

    days = await weather.get_daily_forecast(*PRAGUE, days=3)

    assert [d.date for d in days] == [
        dt.date(2026, 10, 16),
        dt.date(2026, 10, 17),
        dt.date(2026, 10, 18),
    ]
    first = days[0]
    assert first.temperature_max == 17.3
    assert first.temperature_min == 4.9
    assert first.relative_humidity_mean == 84
    assert first.weather_code == 45
    assert first.description == "Fog"
    assert first.sunrise == dt.datetime(2026, 10, 16, 7, 25)
    assert first.sunset == dt.datetime(2026, 10, 16, 18, 9)

    params = route.calls.last.request.url.params
    assert params["forecast_days"] == "3"
    assert params["daily"].split(",") == DAILY_VARIABLES


async def test_get_daily_forecast_allows_missing_values(
    weather: OpenMeteoWeatherClient, respx_mock: respx.MockRouter
) -> None:
    payload = load_fixture("forecast_daily")
    payload["daily"]["weather_code"][2] = None
    payload["daily"]["relative_humidity_2m_mean"][2] = None
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json=payload))

    days = await weather.get_daily_forecast(*PRAGUE, days=3)

    assert days[2].weather_code is None
    assert days[2].description is None
    assert days[2].relative_humidity_mean is None


async def test_get_daily_forecast_columns_of_unequal_length_raise(
    weather: OpenMeteoWeatherClient, respx_mock: respx.MockRouter
) -> None:
    payload = load_fixture("forecast_daily")
    payload["daily"]["sunset"].pop()
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(UpstreamServiceError, match="'daily'"):
        await weather.get_daily_forecast(*PRAGUE, days=3)


@pytest.mark.parametrize("days", [0, 17])
async def test_get_daily_forecast_rejects_invalid_days(
    weather: OpenMeteoWeatherClient, days: int
) -> None:
    with pytest.raises(ValueError, match="between 1 and 16"):
        await weather.get_daily_forecast(*PRAGUE, days=days)
