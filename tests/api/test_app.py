import pytest
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_weather_service
from app.clients.base import GeocodingClient, SearchResult
from app.clients.geonames_geocoding import GeoNamesGeocodingClient
from app.config import Settings
from app.main import create_app, lifespan
from app.schemas.language import Language
from app.schemas.location import Location
from app.schemas.weather import CurrentWeather, DailyForecastDay, Units
from app.services.weather_service import WeatherService
from tests.api.upstream import mock_forecast, mock_geocoding
from tests.doubles import UnavailableCache
from tests.unit.clients.test_geonames_geocoding import FakeGeoNames


async def test_unknown_route_uses_error_format(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}


async def test_wrong_method_uses_error_format(client: AsyncClient) -> None:
    response = await client.post("/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert response.headers["allow"] == "GET"


async def test_openapi_documents_error_responses(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()

    current = schema["paths"]["/api/v1/weather/current"]["get"]
    assert set(current["responses"]) == {"200", "404", "422", "501", "502", "504"}
    assert [p["name"] for p in current["parameters"]] == [
        "city",
        "id",
        "country",
        "region",
        "lang",
        "units",
    ]


async def test_ready_when_cache_is_reachable(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"redis": "ok"}}


async def test_not_ready_when_cache_is_down(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_weather_service] = lambda: WeatherService(
        FakeGeocodingClient(), FakeWeatherClient(), UnavailableCache()
    )

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"redis": "unavailable"}}


async def test_lifespan_wires_the_real_service(
    settings: Settings, respx_mock: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    """Runs the real startup/shutdown (ASGITransport does not), so no dependency overrides.

    Redis is unreachable here (see conftest): the app must still start and answer.
    """
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current")
    app = create_app(settings)

    async with lifespan(app):
        service = app.state.weather_service
        assert isinstance(service, WeatherService)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/weather/current", params={"city": "Prague"})
        assert response.status_code == 200
        assert response.json()["cached"] is False

    assert "running without cache" in caplog.text
    # The shared HTTP client is closed on shutdown.
    assert service._weather._http.is_closed  # type: ignore[attr-defined]


class FakeGeocodingClient(GeocodingClient):
    async def find(
        self, name: str, *, count: int, country_code: str | None, language: Language
    ) -> SearchResult:
        return SearchResult([])

    async def get(self, place_id: int, *, language: Language) -> Location | None:
        return None


class FakeWeatherClient:
    async def get_current(
        self, latitude: float, longitude: float, *, units: Units = Units.METRIC
    ) -> CurrentWeather:
        raise NotImplementedError

    async def get_daily_forecast(
        self, latitude: float, longitude: float, *, days: int = 7, units: Units = Units.METRIC
    ) -> list[DailyForecastDay]:
        raise NotImplementedError


async def test_lookup_by_id_without_provider_support_returns_501(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_weather_service] = lambda: WeatherService(
        GeoNamesGeocodingClient(FakeGeoNames()), FakeWeatherClient()
    )

    response = await client.get("/api/v1/weather/current", params={"id": 703448})

    assert response.status_code == 501
    assert response.json() == {
        "error": {
            "code": "NOT_SUPPORTED",
            "message": "GeoNames does not support looking places up by id.",
        }
    }
