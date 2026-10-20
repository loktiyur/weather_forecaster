"""respx helpers that make the external APIs answer with recorded responses."""

import httpx
import respx

from app.config import Settings
from tests.fixtures import load_fixture

GEOCODING_URL = Settings.model_fields["open_meteo_geocoding_url"].default
PLACE_URL = Settings.model_fields["open_meteo_place_url"].default
FORECAST_URL = Settings.model_fields["open_meteo_forecast_url"].default


def mock_geocoding(respx_mock: respx.MockRouter, fixture: str = "geocoding_prague") -> respx.Route:
    return respx_mock.get(GEOCODING_URL).mock(
        return_value=httpx.Response(200, json=load_fixture(fixture))
    )


def mock_forecast(respx_mock: respx.MockRouter, fixture: str) -> respx.Route:
    return respx_mock.get(FORECAST_URL).mock(
        return_value=httpx.Response(200, json=load_fixture(fixture))
    )


def mock_place(respx_mock: respx.MockRouter, fixture: str) -> respx.Route:
    return respx_mock.get(PLACE_URL).mock(
        return_value=httpx.Response(200, json=load_fixture(fixture))
    )
