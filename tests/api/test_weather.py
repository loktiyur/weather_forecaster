import httpx
import pytest
import respx
from httpx import AsyncClient

from tests.api.upstream import GEOCODING_URL, PLACE_URL, mock_forecast, mock_geocoding, mock_place
from tests.fixtures import load_fixture
from tests.logs import json_logs

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
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current").mock(
        return_value=httpx.Response(500, json={"error": True, "reason": "internal db error"})
    )

    with json_logs() as lines:
        response = await client.get(CURRENT, params={"city": "Prague"})

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "UPSTREAM_ERROR"
    # Internal details are logged, not leaked to the client.
    assert "internal db error" not in error["message"]
    [logged] = [line for line in lines() if line["event"] == "upstream_error"]
    assert logged["service"] == "Open-Meteo Forecast"
    assert logged["detail"] == "HTTP 500: internal db error"


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
        ({"city": ""}, "city"),
        ({"city": "   "}, "city"),
        ({"city": "x" * 101}, "city"),
        ({"city": "10001"}, "city"),
        ({"city": "123"}, "city"),
        ({"city": "-- 42 --"}, "city"),
        ({"city": "Prague", "country": "CZE"}, "country"),
        ({"city": "Prague", "country": "1Z"}, "country"),
        ({"city": "Prague", "units": "kelvin"}, "units"),
        ({"city": "Prague", "region": "x" * 101}, "region"),
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


async def test_city_without_letters_is_not_sent_upstream(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    response = await client.get(CURRENT, params={"city": "75001"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["message"] == (
        "Value error, must contain at least one letter"
    )
    assert not respx_mock.calls


@pytest.mark.parametrize("city", ["Київ", "東京", "'s-Hertogenbosch", "Saint-Étienne"])
async def test_city_names_in_any_script_are_accepted(
    client: AsyncClient, respx_mock: respx.MockRouter, city: str
) -> None:
    mock_geocoding(respx_mock, "geocoding_not_found")

    response = await client.get(CURRENT, params={"city": city})

    assert response.status_code == 404  # validation passed; the (mocked) geocoder found nothing


async def test_region_selects_the_place(client: AsyncClient, respx_mock: respx.MockRouter) -> None:
    geocoding = mock_geocoding(respx_mock, "geocoding_odessa")
    mock_forecast(respx_mock, "forecast_current")

    response = await client.get(
        CURRENT, params={"city": "Odessa", "country": "US", "region": "Missouri"}
    )

    assert response.status_code == 200
    location = response.json()["location"]
    assert (location["name"], location["region"]) == ("Odessa", "Missouri")
    assert geocoding.calls.last.request.url.params["countryCode"] == "US"


async def test_country_name_returns_not_a_city(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(GEOCODING_URL).respond(
        json={
            "results": [
                {"name": "Germany", "latitude": 51.5, "longitude": 10.5, "feature_code": "PCLI"}
            ]
        }
    )

    response = await client.get(FORECAST, params={"city": "Germany"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_A_CITY", "message": "'Germany' is a country, not a city."}
    }


async def test_unknown_region_returns_404(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock, "geocoding_odessa")

    response = await client.get(CURRENT, params={"city": "Odessa", "region": "Ohio"})

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "No place found for 'Odessa, Ohio'."


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


async def test_city_or_id_is_required(client: AsyncClient) -> None:
    response = await client.get(CURRENT, params={"units": "metric"})

    assert response.status_code == 422
    [detail] = response.json()["error"]["details"]
    assert detail["message"] == "Value error, either `city` or `id` is required"


async def test_id_selects_the_place_in_the_requested_language(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    place = mock_place(respx_mock, "place_kyiv_uk")
    mock_forecast(respx_mock, "forecast_current")

    response = await client.get(CURRENT, params={"id": 703448, "lang": "uk", "city": "ignored"})

    assert response.status_code == 200
    body = response.json()
    assert (body["location"]["id"], body["location"]["name"]) == (703448, "Київ")
    assert body["current"]["description"] == "Ясне небо"  # weather_code 0 in the fixture
    assert body["units"]["wind_speed"] == "км/год"
    assert place.calls.last.request.url.params["language"] == "uk"


async def test_unknown_id_returns_location_not_found(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(PLACE_URL).respond(400, json={"error": True, "reason": "Location ID not found."})

    response = await client.get(FORECAST, params={"id": 999999999})

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "LOCATION_NOT_FOUND", "message": "No place found with id 999999999."}
    }


async def test_cyrillic_name_with_english_interface(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    # The English search finds nothing for "Київ"; the Ukrainian one does, and the place is
    # then looked up by id in English.
    def geocoding(request: httpx.Request) -> httpx.Response:
        if request.url.params["language"] == "uk":
            return httpx.Response(200, json=load_fixture("geocoding_kyiv_uk"))
        return httpx.Response(200, json={})

    respx_mock.get(GEOCODING_URL).mock(side_effect=geocoding)
    mock_place(respx_mock, "place_kyiv_en")
    mock_forecast(respx_mock, "forecast_current")

    response = await client.get(CURRENT, params={"city": "Київ"})

    assert response.status_code == 200
    location = response.json()["location"]
    assert (location["name"], location["country"]) == ("Kyiv", "Ukraine")
    assert response.json()["current"]["description"] == "Clear sky"


async def test_unsupported_language_is_rejected(client: AsyncClient) -> None:
    response = await client.get(CURRENT, params={"city": "Prague", "lang": "de"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "lang"
