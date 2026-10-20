import httpx

from app.clients.base import GeocodingClient
from app.clients.geonames_geocoding import GeoNamesGeocodingClient
from app.clients.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.config import Settings


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
