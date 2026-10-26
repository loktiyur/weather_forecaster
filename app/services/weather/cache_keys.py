"""What the weather service caches: the key layout and how long each kind of data stays.

These are weather decisions, so they live here; `core/cache` only knows how to cache
(ARCHITECTURE.md §6). One place, so keys never drift apart.
"""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.language import Language
from app.services.weather.schemas import Units


@dataclass(frozen=True)
class CacheTtls:
    """How long each kind of data stays in the cache, in seconds."""

    geocoding: int = 7 * 24 * 3600
    current: int = 600
    forecast: int = 3600

    @classmethod
    def from_settings(cls, settings: Settings) -> "CacheTtls":
        return cls(
            geocoding=settings.cache_ttl_geocoding_seconds,
            current=settings.cache_ttl_current_seconds,
            forecast=settings.cache_ttl_forecast_seconds,
        )


def geocoding_key(
    city: str, country_code: str | None, region: str | None = None, language: Language = Language.EN
) -> str:
    # "  Prague " and "prague" are the same place, so they share one entry. The language is
    # part of the key: the names inside the entry are in that language.
    key = f"geo:{language}:{city.strip().lower()}:{(country_code or '').upper()}"
    # The region is appended only when given, so keys without one stay short.
    return f"{key}:{region.strip().lower()}" if region else key


def place_key(location_id: int, language: Language) -> str:
    return f"place:{location_id}:{language}"


def current_weather_key(latitude: float, longitude: float, units: Units) -> str:
    # Rounded to ~1 km, so nearby coordinates share an entry. Weather data has no language:
    # descriptions are translated when the response is built, so all languages share it.
    return f"weather:current:{latitude:.2f}:{longitude:.2f}:{units}"


def forecast_key(latitude: float, longitude: float, days: int, units: Units) -> str:
    return f"weather:forecast:{latitude:.2f}:{longitude:.2f}:{days}:{units}"
