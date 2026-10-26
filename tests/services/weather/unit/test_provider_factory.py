import httpx

from app.core.config import Settings
from app.services.weather.providers.factory import create_geocoding_client
from app.services.weather.providers.geonames_geocoding import GeoNamesGeocodingClient
from app.services.weather.providers.open_meteo_geocoding import OpenMeteoGeocodingClient


def make_settings(**overrides: object) -> Settings:
    # _env_file=None: tests must not depend on the developer's local .env
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_default_provider_is_open_meteo(http: httpx.AsyncClient) -> None:
    settings = make_settings()

    assert isinstance(create_geocoding_client(settings, http), OpenMeteoGeocodingClient)


def test_geonames_provider(http: httpx.AsyncClient) -> None:
    settings = make_settings(geocoding_provider="geonames", geonames_username="demo")

    assert isinstance(create_geocoding_client(settings, http), GeoNamesGeocodingClient)
