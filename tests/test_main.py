import tomllib

import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import _without_credentials, create_app, lifespan
from app.services.weather.service import WeatherService
from tests.logs import json_logs
from tests.services.weather.api.upstream import mock_forecast, mock_geocoding


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


async def test_lifespan_wires_the_real_service(
    settings: Settings, respx_mock: respx.MockRouter
) -> None:
    """Runs the real startup/shutdown (ASGITransport does not), so no dependency overrides.

    Redis is unreachable here (see conftest): the app must still start and answer.
    """
    mock_geocoding(respx_mock)
    mock_forecast(respx_mock, "forecast_current")
    app = create_app(settings)

    with json_logs() as lines:
        async with lifespan(app):
            service = app.state.weather_service
            assert isinstance(service, WeatherService)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/weather/current", params={"city": "Prague"})
                ready = await client.get("/health/ready")
            assert response.status_code == 200
            assert response.json()["cached"] is False
            # Readiness asks the cache the lifespan created, and that Redis is unreachable.
            assert ready.json() == {"status": "unavailable", "checks": {"redis": "unavailable"}}

    [warning] = [line for line in lines() if line["event"] == "redis_unreachable"]
    assert warning["redis"] == "redis://localhost:1/0"
    # The shared HTTP client is closed on shutdown.
    assert service._weather._http.is_closed  # type: ignore[attr-defined]


def test_api_version_matches_pyproject() -> None:
    # The release workflow checks the tag against pyproject.toml; /docs must show the same.
    with open("pyproject.toml", "rb") as file:
        version = tomllib.load(file)["project"]["version"]

    assert create_app(Settings(_env_file=None)).version == version


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("redis://:secret@cache:6379/0", "redis://cache:6379/0"),
        ("redis://user:secret@cache:6379/0", "redis://cache:6379/0"),
        ("redis://localhost:6379/0", "redis://localhost:6379/0"),
    ],
)
def test_redis_url_is_logged_without_credentials(url: str, expected: str) -> None:
    assert _without_credentials(url) == expected
