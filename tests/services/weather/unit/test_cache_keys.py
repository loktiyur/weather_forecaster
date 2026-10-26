from app.core.config import Settings
from app.services.weather.cache_keys import (
    CacheTtls,
    current_weather_key,
    forecast_key,
    geocoding_key,
)
from app.services.weather.schemas import Units


def test_geocoding_key_is_normalised() -> None:
    assert geocoding_key("  Prague ", None) == "geo:en:prague:"
    assert geocoding_key("PRAGUE", "cz") == "geo:en:prague:CZ"
    assert geocoding_key("Odessa", "US", " Texas ") == "geo:en:odessa:US:texas"


def test_weather_keys_round_coordinates() -> None:
    assert current_weather_key(50.08804, 14.42076, Units.METRIC) == (
        "weather:current:50.09:14.42:metric"
    )
    assert forecast_key(50.08804, 14.42076, 3, Units.IMPERIAL) == (
        "weather:forecast:50.09:14.42:3:imperial"
    )


def test_cache_ttls_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        cache_ttl_geocoding_seconds=1,
        cache_ttl_current_seconds=2,
        cache_ttl_forecast_seconds=3,
    )

    assert CacheTtls.from_settings(settings) == CacheTtls(geocoding=1, current=2, forecast=3)
