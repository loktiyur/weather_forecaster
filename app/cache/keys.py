"""Cache key layout (see ARCHITECTURE.md §6). One place, so keys never drift apart."""

from app.schemas.language import Language
from app.schemas.weather import Units


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
