import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.clients.base import GeocodingClient
from app.core.exceptions import CityNotFoundError
from app.schemas.location import Location
from app.schemas.weather import CurrentWeather, DailyForecastDay, Units
from app.services.weather_service import WeatherService

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
