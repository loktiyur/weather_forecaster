import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.cache.base import Cache
from app.clients.base import GeocodingClient, SearchResult
from app.config import Settings
from app.core.exceptions import CityNotFoundError, LocationNotFoundError, NotACityError
from app.schemas.language import Language
from app.schemas.location import Location
from app.schemas.weather import CurrentWeather, DailyForecastDay, Units
from app.services.weather_service import CacheTtls, WeatherService
from tests.doubles import InMemoryCache, UnavailableCache
from tests.logs import json_logs

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
    def __init__(
        self,
        places: list[Location],
        country: str | None = None,
        by_id: dict[int, Location] | None = None,
    ) -> None:
        self.places = places
        self.country = country
        self.by_id = by_id or {}
        self.calls: list[dict[str, Any]] = []

    async def find(
        self, name: str, *, count: int, country_code: str | None, language: Language
    ) -> SearchResult:
        self.calls.append({"name": name, "count": count, "country_code": country_code})
        return SearchResult(self.places[:count], country=self.country)

    async def get(self, place_id: int, *, language: Language) -> Location | None:
        self.calls.append({"id": place_id, "language": language})
        return self.by_id.get(place_id)


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


ODESSA_TX = Location(
    name="Odessa", country_code="US", region="Texas", latitude=31.85, longitude=-102.37
)
ODESSA_MO = Location(
    name="Odessa", country_code="US", region="Missouri", latitude=38.99, longitude=-93.95
)


async def test_region_selects_one_of_several_same_name_places() -> None:
    geocoding = FakeGeocoding([ODESSA_TX, ODESSA_MO])
    service = WeatherService(geocoding, FakeWeather(), cache=InMemoryCache())

    result = await service.get_current("Odessa", country_code="US", region="missouri")

    assert result.location == ODESSA_MO
    assert geocoding.calls == [{"name": "Odessa", "count": 20, "country_code": "US"}]


async def test_region_lookup_ignores_places_that_only_contain_the_name() -> None:
    saint_paris = Location(
        name="Saint Paris", country_code="US", region="Ohio", latitude=40.13, longitude=-83.96
    )
    paris = Location(
        name="Paris", country_code="US", region="Ohio", latitude=40.8, longitude=-81.16
    )
    service = WeatherService(FakeGeocoding([saint_paris, paris]), FakeWeather())

    result = await service.get_current("paris", country_code="US", region="Ohio")

    assert result.location == paris


async def test_a_country_name_raises_not_a_city() -> None:
    germany_georgia = Location(
        name="Germany", country_code="US", region="Georgia", latitude=34.9, longitude=-83.47
    )
    cache = InMemoryCache()
    service = WeatherService(
        FakeGeocoding([germany_georgia], country="Germany"), FakeWeather(), cache
    )

    with pytest.raises(NotACityError, match="'Germany' is a country"):
        await service.get_current("germany")
    assert cache.values == {}  # errors are not cached

    # The search still lists the towns, so the user can pick one of them.
    assert await service.search_locations("germany") == [germany_georgia]


async def test_unknown_region_raises_city_not_found() -> None:
    service = WeatherService(FakeGeocoding([ODESSA_TX, ODESSA_MO]), FakeWeather())

    with pytest.raises(CityNotFoundError, match="Odessa, Ohio"):
        await service.get_forecast("Odessa", country_code="US", region="Ohio")


async def test_places_with_and_without_region_are_cached_separately() -> None:
    cache = InMemoryCache()
    service = WeatherService(FakeGeocoding([ODESSA_TX, ODESSA_MO]), FakeWeather(), cache=cache)

    await service.get_current("Odessa", country_code="US")
    await service.get_current("Odessa", country_code="US", region="Missouri")

    assert Location.model_validate_json(cache.values["geo:en:odessa:US"]) == ODESSA_TX
    assert Location.model_validate_json(cache.values["geo:en:odessa:US:missouri"]) == ODESSA_MO


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
    assert cache.ttls == {"geo:en:prague:": 100, "weather:current:50.08:14.42:imperial": 10}
    assert Location.model_validate_json(cache.values["geo:en:prague:"]) == PRAGUE


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


async def test_unavailable_cache_falls_back_to_the_clients() -> None:
    weather = FakeWeather()
    service = WeatherService(FakeGeocoding([PRAGUE]), weather, UnavailableCache())

    with json_logs() as lines:
        result = await service.get_current("Prague")

    assert result.current == CURRENT
    assert result.cached is False
    assert len(weather.calls) == 1
    warnings = [line for line in lines() if line["event"] == "cache_unavailable"]
    assert {(w["operation"], w["key"]) for w in warnings} == {
        ("read", "geo:en:prague:"),
        ("write", "geo:en:prague:"),
        ("read", "weather:current:50.08:14.42:metric"),
        ("write", "weather:current:50.08:14.42:metric"),
    }
    assert all(w["error"] == "cache is down" for w in warnings)


async def test_unreadable_cache_entry_is_treated_as_a_miss() -> None:
    cache = InMemoryCache(values={"geo:en:prague:": '{"old": "format"}'})
    geocoding = FakeGeocoding([PRAGUE])
    service = WeatherService(geocoding, FakeWeather(), cache)

    with json_logs() as lines:
        result = await service.get_current("Prague")

    assert result.location == PRAGUE
    assert len(geocoding.calls) == 1
    assert Location.model_validate_json(cache.values["geo:en:prague:"]) == PRAGUE  # overwritten
    [warning] = [line for line in lines() if line["event"] == "cache_entry_unreadable"]
    assert warning["key"] == "geo:en:prague:"


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


KYIV = Location(id=703448, name="Київ", country_code="UA", latitude=50.45, longitude=30.52)


async def test_location_id_is_looked_up_and_cached_per_language() -> None:
    geocoding = FakeGeocoding([], by_id={703448: KYIV})
    cache = InMemoryCache()
    service = WeatherService(geocoding, FakeWeather(), cache=cache)

    result = await service.get_current(location_id=703448, language=Language.UK)
    await service.get_current(location_id=703448, language=Language.UK)

    assert result.location == KYIV
    assert geocoding.calls == [{"id": 703448, "language": Language.UK}]  # 2nd call: cache
    assert Location.model_validate_json(cache.values["place:703448:uk"]) == KYIV


async def test_unknown_location_id_raises() -> None:
    service = WeatherService(FakeGeocoding([]), FakeWeather())

    with pytest.raises(LocationNotFoundError, match="id 42"):
        await service.get_forecast(location_id=42)


async def test_city_or_location_id_is_required() -> None:
    service = WeatherService(FakeGeocoding([PRAGUE]), FakeWeather())

    with pytest.raises(ValueError, match="either city or location_id"):
        await service.get_current()


async def test_texts_are_translated_but_weather_is_cached_once_for_all_languages() -> None:
    weather = FakeWeather()
    service = WeatherService(FakeGeocoding([PRAGUE]), weather, cache=InMemoryCache())

    english = await service.get_current("Prague")
    czech = await service.get_current("Prague", language=Language.CS)
    forecast = await service.get_forecast("Prague", language=Language.RU, days=1)

    assert (english.current.description, english.units.wind_speed) == ("Clear sky", "km/h")
    assert (czech.current.description, czech.cached) == ("Jasno", True)
    assert forecast.daily[0].description == "Пасмурно"
    assert forecast.units.wind_speed == "км/ч"
    assert [call["method"] for call in weather.calls] == ["current", "daily"]


async def test_forecast_day_without_code_has_no_description() -> None:
    class NoCodeWeather(FakeWeather):
        async def get_daily_forecast(
            self, latitude: float, longitude: float, *, days: int = 7, units: Units = Units.METRIC
        ) -> list[DailyForecastDay]:
            return [DAY.model_copy(update={"weather_code": None, "description": None})]

    service = WeatherService(FakeGeocoding([PRAGUE]), NoCodeWeather())

    result = await service.get_forecast("Prague", language=Language.UK)

    assert result.daily[0].description is None
