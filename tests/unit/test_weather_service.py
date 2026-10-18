import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.cache.base import Cache
from app.clients.base import GeocodingClient
from app.config import Settings
from app.core.exceptions import CityNotFoundError
from app.schemas.location import Location
from app.schemas.weather import CurrentWeather, DailyForecastDay, Units
from app.services.weather_service import CacheTtls, WeatherService
from tests.doubles import InMemoryCache, UnavailableCache

PRAGUE = Location(name="Prague", country_code="CZ", latitude=50.08, longitude=14.42)
CURRENT = CurrentWeather(
    time=dt.datetime(2026, 10, 16, 14, 0),
    temperature=16.0,
    apparent_temperature=15.0,
    relative_humidity=60,
    wind_speed=3.0,
    weather_code=0,
    description="Clear sky",
    is_day=True,
)
DAY = DailyForecastDay(
    date=dt.date(2026, 10, 16),
    temperature_max=17.0,
    temperature_min=5.0,
    relative_humidity_mean=80,
    weather_code=3,
    description="Overcast",
    sunrise=None,
    sunset=None,
)


class FakeGeocoding(GeocodingClient):
    def __init__(self, places: list[Location]) -> None:
        self.places = places
        self.calls: list[dict[str, Any]] = []

    async def search(
        self, name: str, *, count: int = 5, country_code: str | None = None
    ) -> list[Location]:
        self.calls.append({"name": name, "count": count, "country_code": country_code})
        return self.places[:count]


@dataclass
class FakeWeather:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def get_current(
        self, latitude: float, longitude: float, *, units: Units = Units.METRIC
    ) -> CurrentWeather:
        self.calls.append({"method": "current", "lat": latitude, "lon": longitude, "units": units})
        return CURRENT

    async def get_daily_forecast(
        self, latitude: float, longitude: float, *, days: int = 7, units: Units = Units.METRIC
    ) -> list[DailyForecastDay]:
        self.calls.append({"method": "daily", "days": days, "units": units})
        return [DAY] * days


async def test_get_current_geocodes_then_fetches_weather() -> None:
    geocoding, weather = FakeGeocoding([PRAGUE]), FakeWeather()
    service = WeatherService(geocoding, weather)

    result = await service.get_current("Prague", country_code="CZ", units=Units.IMPERIAL)

    assert geocoding.calls == [{"name": "Prague", "count": 1, "country_code": "CZ"}]
    assert weather.calls == [
        {"method": "current", "lat": 50.08, "lon": 14.42, "units": Units.IMPERIAL}
    ]
    assert result.location == PRAGUE
    assert result.current == CURRENT
    assert result.units.temperature == "°F"


async def test_get_forecast_passes_days_and_units() -> None:
    weather = FakeWeather()
    service = WeatherService(FakeGeocoding([PRAGUE]), weather)

    result = await service.get_forecast("Prague", days=3)

    assert weather.calls == [{"method": "daily", "days": 3, "units": Units.METRIC}]
    assert len(result.daily) == 3
    assert result.units.temperature == "°C"


async def test_unknown_city_does_not_call_weather_api() -> None:
    weather = FakeWeather()
    service = WeatherService(FakeGeocoding([]), weather)

    with pytest.raises(CityNotFoundError):
        await service.get_current("Nowhere")
    assert weather.calls == []


async def test_search_locations_uses_limit() -> None:
    other = PRAGUE.model_copy(update={"country_code": "US"})
    geocoding = FakeGeocoding([PRAGUE, other, PRAGUE])
    service = WeatherService(geocoding, FakeWeather())

    results = await service.search_locations("Prague", limit=2, country_code=None)

    assert results == [PRAGUE, other]
    assert geocoding.calls[0]["count"] == 2


# --- caching -------------------------------------------------------------------------------


async def test_without_cache_every_call_hits_the_clients() -> None:
    weather = FakeWeather()
    service = WeatherService(FakeGeocoding([PRAGUE]), weather)

    first = await service.get_current("Prague")
    second = await service.get_current("Prague")

    assert len(weather.calls) == 2
    assert first.cached is second.cached is False


async def test_cache_miss_stores_results_with_their_ttls() -> None:
    cache = InMemoryCache()
    service = WeatherService(
        FakeGeocoding([PRAGUE]),
        FakeWeather(),
        cache,
        CacheTtls(geocoding=100, current=10, forecast=50),
    )

    result = await service.get_current("Prague", units=Units.IMPERIAL)

    assert result.cached is False
    assert cache.ttls == {"geo:prague:": 100, "weather:current:50.08:14.42:imperial": 10}
    assert Location.model_validate_json(cache.values["geo:prague:"]) == PRAGUE


async def test_cache_hit_skips_both_clients() -> None:
    cache = InMemoryCache()
    geocoding, weather = FakeGeocoding([PRAGUE]), FakeWeather()
    service = WeatherService(geocoding, weather, cache)
    await service.get_current("Prague")

    result = await service.get_current("  PRAGUE ")

    assert result.cached is True
    assert result.current == CURRENT
    assert len(geocoding.calls) == 1
    assert len(weather.calls) == 1


async def test_geocoding_entry_is_shared_between_current_and_forecast() -> None:
    geocoding = FakeGeocoding([PRAGUE])
    service = WeatherService(geocoding, FakeWeather(), InMemoryCache())

    await service.get_current("Prague")
    forecast = await service.get_forecast("Prague", days=2)

    assert len(geocoding.calls) == 1
    assert forecast.cached is False  # the forecast itself was not cached yet


async def test_forecast_is_cached_per_number_of_days() -> None:
    cache, weather = InMemoryCache(), FakeWeather()
    service = WeatherService(FakeGeocoding([PRAGUE]), weather, cache)

    await service.get_forecast("Prague", days=2)
    again = await service.get_forecast("Prague", days=2)
    await service.get_forecast("Prague", days=3)

    assert again.cached is True
    assert len(again.daily) == 2
    assert [call["days"] for call in weather.calls] == [2, 3]
    assert cache.ttls["weather:forecast:50.08:14.42:2:metric"] == CacheTtls().forecast


async def test_unavailable_cache_falls_back_to_the_clients(
    caplog: pytest.LogCaptureFixture,
) -> None:
    weather = FakeWeather()
    service = WeatherService(FakeGeocoding([PRAGUE]), weather, UnavailableCache())

    result = await service.get_current("Prague")

    assert result.current == CURRENT
    assert result.cached is False
    assert len(weather.calls) == 1
    assert "Cache unavailable" in caplog.text


async def test_unreadable_cache_entry_is_treated_as_a_miss(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cache = InMemoryCache(values={"geo:prague:": '{"old": "format"}'})
    geocoding = FakeGeocoding([PRAGUE])
    service = WeatherService(geocoding, FakeWeather(), cache)

    result = await service.get_current("Prague")

    assert result.location == PRAGUE
    assert len(geocoding.calls) == 1
    assert Location.model_validate_json(cache.values["geo:prague:"]) == PRAGUE  # overwritten
    assert "unreadable cache entry geo:prague:" in caplog.text


async def test_unknown_city_is_not_cached() -> None:
    cache = InMemoryCache()
    service = WeatherService(FakeGeocoding([]), FakeWeather(), cache)

    with pytest.raises(CityNotFoundError):
        await service.get_current("Nowhere")
    assert cache.values == {}


@pytest.mark.parametrize(
    ("cache", "expected"), [(None, False), (InMemoryCache(), True), (UnavailableCache(), False)]
)
async def test_cache_is_reachable(cache: Cache | None, expected: bool) -> None:
    service = WeatherService(FakeGeocoding([PRAGUE]), FakeWeather(), cache)

    assert await service.cache_is_reachable() is expected


def test_cache_ttls_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        cache_ttl_geocoding_seconds=1,
        cache_ttl_current_seconds=2,
        cache_ttl_forecast_seconds=3,
    )

    assert CacheTtls.from_settings(settings) == CacheTtls(geocoding=1, current=2, forecast=3)
