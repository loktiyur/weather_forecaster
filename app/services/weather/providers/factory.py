import httpx

from app.core.config import Settings
from app.services.weather.providers.base import GeocodingClient
from app.services.weather.providers.geonames_geocoding import GeoNamesGeocodingClient
from app.services.weather.providers.open_meteo_geocoding import OpenMeteoGeocodingClient


def create_geocoding_client(settings: Settings, http: httpx.AsyncClient) -> GeocodingClient:
    """Pick the geocoding provider configured by GEOCODING_PROVIDER."""
    if settings.geocoding_provider == "geonames":
        # Settings validation guarantees the username is set for this provider.
        assert settings.geonames_username is not None
        return GeoNamesGeocodingClient.from_username(
            settings.geonames_username, timeout=settings.http_timeout_seconds
        )
    return OpenMeteoGeocodingClient(
        http, settings.open_meteo_geocoding_url, settings.open_meteo_place_url
    )
