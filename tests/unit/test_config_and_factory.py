import httpx
import pytest
from pydantic import ValidationError

from app.clients.factory import create_geocoding_client
from app.clients.geonames_geocoding import GeoNamesGeocodingClient
from app.clients.http import create_http_client
from app.clients.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.config import Settings, get_settings


def make_settings(**overrides: object) -> Settings:
    # _env_file=None: tests must not depend on the developer's local .env
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_default_provider_is_open_meteo(http: httpx.AsyncClient) -> None:
    settings = make_settings()

    assert isinstance(create_geocoding_client(settings, http), OpenMeteoGeocodingClient)


def test_geonames_provider(http: httpx.AsyncClient) -> None:
    settings = make_settings(geocoding_provider="geonames", geonames_username="demo")

    assert isinstance(create_geocoding_client(settings, http), GeoNamesGeocodingClient)


def test_geonames_without_username_is_rejected() -> None:
    with pytest.raises(ValidationError, match="GEONAMES_USERNAME is required"):
        make_settings(geocoding_provider="geonames")


def test_settings_are_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "2.5")

    assert make_settings().http_timeout_seconds == 2.5


async def test_http_client_uses_configured_timeout() -> None:
    async with create_http_client(make_settings(http_timeout_seconds=3)) as http:
        assert http.timeout.read == 3


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
