import httpx
import pytest
import respx
from httpx import AsyncClient

from tests.api.upstream import mock_forecast, mock_geocoding

CURRENT = "/api/v1/weather/current"
FORECAST = "/api/v1/weather/forecast"


async def test_current_weather(client: AsyncClient, respx_mock: respx.MockRouter) -> None:
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current")

    response = await client.get(CURRENT, params={"city": "Prague"})

    assert response.status_code == 200
    body = response.json()
    assert body["location"]["name"] == "Prague"
    assert body["location"]["country_code"] == "CZ"
    assert body["current"] == {
        "time": "2026-10-16T14:15:00",
        "temperature": 16.0,
        "apparent_temperature": 15.2,
        "relative_humidity": 60.0,
        "wind_speed": 2.6,
        "weather_code": 0,
        "description": "Clear sky",
        "is_day": True,
    }
    assert body["units"] == {"temperature": "°C", "wind_speed": "km/h"}


async def test_current_weather_passes_query_to_upstream(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    geocoding = mock_geocoding(respx_mock)
    forecast = mock_forecast(respx_mock, "forecast_current")

    response = await client.get(
        CURRENT, params={"city": "  Prague ", "country": "cz", "units": "imperial"}
    )

    assert response.status_code == 200
    assert response.json()["units"] == {"temperature": "°F", "wind_speed": "mph"}
    geo_params = geocoding.calls.last.request.url.params
    assert geo_params["name"] == "Prague"
    assert geo_params["countryCode"] == "CZ"
    forecast_params = forecast.calls.last.request.url.params
    assert forecast_params["latitude"] == "50.08804"
    assert forecast_params["temperature_unit"] == "fahrenheit"


async def test_forecast(client: AsyncClient, respx_mock: respx.MockRouter) -> None:
    mock_geocoding(respx_mock)
    forecast = mock_forecast(respx_mock, "forecast_daily")

    response = await client.get(FORECAST, params={"city": "Prague", "days": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["location"]["name"] == "Prague"
    assert [day["date"] for day in body["daily"]] == ["2026-10-16", "2026-10-17", "2026-10-18"]
    assert body["daily"][0]["description"] == "Fog"
    assert forecast.calls.last.request.url.params["forecast_days"] == "3"


async def test_forecast_defaults_to_7_days(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock)
    forecast = mock_forecast(respx_mock, "forecast_daily")

    await client.get(FORECAST, params={"city": "Prague"})

    assert forecast.calls.last.request.url.params["forecast_days"] == "7"


async def test_unknown_city_returns_404(client: AsyncClient, respx_mock: respx.MockRouter) -> None:
    mock_geocoding(respx_mock, "geocoding_not_found")

    response = await client.get(CURRENT, params={"city": "Qwertyuiopxyz"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "CITY_NOT_FOUND", "message": "No place found for 'Qwertyuiopxyz'."}
    }


async def test_upstream_failure_returns_502(
    client: AsyncClient, respx_mock: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current").mock(
        return_value=httpx.Response(500, json={"error": True, "reason": "internal db error"})
    )

    response = await client.get(CURRENT, params={"city": "Prague"})

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_ERROR"
    # Internal details are logged, not leaked to the client.
    assert "internal db error" not in error["message"]
    assert "internal db error" in caplog.text


async def test_upstream_timeout_returns_504(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock).mock(side_effect=httpx.ReadTimeout("slow"))

    response = await client.get(CURRENT, params={"city": "Prague"})

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({}, "city"),
        ({"city": ""}, "city"),
        ({"city": "   "}, "city"),
        ({"city": "x" * 101}, "city"),
        ({"city": "Prague", "country": "CZE"}, "country"),
        ({"city": "Prague", "country": "1Z"}, "country"),
        ({"city": "Prague", "units": "kelvin"}, "units"),
    ],
)
async def test_current_weather_validation(
    client: AsyncClient, params: dict[str, str], field: str
) -> None:
    response = await client.get(CURRENT, params=params)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [d["field"] for d in error["details"]] == [field]
    assert error["details"][0]["location"] == "query"


@pytest.mark.parametrize("days", ["0", "17", "seven"])
async def test_forecast_days_validation(client: AsyncClient, days: str) -> None:
    response = await client.get(FORECAST, params={"city": "Prague", "days": days})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "days"


async def test_validation_reports_all_invalid_fields(client: AsyncClient) -> None:
    response = await client.get(
        FORECAST, params={"city": "Prague", "country": "CZE", "units": "kelvin", "days": 40}
    )

    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert fields == {"country", "units", "days"}


async def test_second_request_is_served_from_cache(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    geocoding = mock_geocoding(respx_mock)
    forecast = mock_forecast(respx_mock, "forecast_current")

    first = await client.get(CURRENT, params={"city": "Prague"})
    second = await client.get(CURRENT, params={"city": "prague"})

    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["current"] == first.json()["current"]
    assert geocoding.call_count == 1
    assert forecast.call_count == 1


@pytest.mark.parametrize(
    ("path", "fixture", "max_age"),
    [(CURRENT, "forecast_current", 600), (FORECAST, "forecast_daily", 3600)],
)
async def test_success_responses_carry_cache_control(
    client: AsyncClient, respx_mock: respx.MockRouter, path: str, fixture: str, max_age: int
) -> None:
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, fixture)

    response = await client.get(path, params={"city": "Prague", "days": 3})

    assert response.headers["cache-control"] == f"public, max-age={max_age}"


async def test_error_responses_have_no_cache_control(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock, "geocoding_not_found")

    response = await client.get(CURRENT, params={"city": "Qwertyuiopxyz"})

    assert response.status_code == 404
    assert "cache-control" not in response.headers
