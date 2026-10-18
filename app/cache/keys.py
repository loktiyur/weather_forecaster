"""Cache key layout (see ARCHITECTURE.md §6). One place, so keys never drift apart."""

from app.schemas.weather import Units


def geocoding_key(city: str, country_code: str | None) -> str:
    # "  Prague " and "prague" are the same place, so they share one entry.
    return f"geo:{city.strip().lower()}:{(country_code or '').upper()}"


def current_weather_key(latitude: float, longitude: float, units: Units) -> str:
    # Rounded to ~1 km, so nearby coordinates share an entry.
    return f"weather:current:{latitude:.2f}:{longitude:.2f}:{units}"


def forecast_key(latitude: float, longitude: float, days: int, units: Units) -> str:
    return f"weather:forecast:{latitude:.2f}:{longitude:.2f}:{days}:{units}"
