import respx
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app, lifespan
from app.services.weather_service import WeatherService
from tests.api.upstream import mock_forecast, mock_geocoding


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
    assert set(current["responses"]) == {"200", "404", "422", "502", "504"}
    assert [p["name"] for p in current["parameters"]] == ["city", "country", "units"]


async def test_lifespan_wires_the_real_service(respx_mock: respx.MockRouter) -> None:
    """Runs the real startup/shutdown (ASGITransport does not), so no dependency overrides."""
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current")
    app = create_app(Settings(_env_file=None))

    async with lifespan(app):
        service = app.state.weather_service
        assert isinstance(service, WeatherService)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/weather/current", params={"city": "Prague"})
        assert response.status_code == 200

    # The shared HTTP client is closed on shutdown.
    assert service._weather._http.is_closed  # type: ignore[attr-defined]
