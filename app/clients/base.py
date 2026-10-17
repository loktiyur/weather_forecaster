from abc import ABC, abstractmethod
from typing import Protocol

from app.core.exceptions import CityNotFoundError
from app.schemas.location import Location
from app.schemas.weather import CurrentWeather, DailyForecastDay, Units


class GeocodingClient(ABC):
    """Turns a place name into coordinates. One implementation per provider."""

    @abstractmethod
    async def search(
        self, name: str, *, count: int = 5, country_code: str | None = None
    ) -> list[Location]:
        """Return up to `count` candidate places, best match first. Empty list if none."""

    async def geocode(self, name: str, *, country_code: str | None = None) -> Location:
        """Return the best match or raise `CityNotFoundError`."""
        results = await self.search(name, count=1, country_code=country_code)
        if not results:
            raise CityNotFoundError(name)
        return results[0]


class WeatherClient(Protocol):
    """Weather data for coordinates. `OpenMeteoWeatherClient` satisfies it structurally."""

    async def get_current(
        self, latitude: float, longitude: float, *, units: Units = Units.METRIC
    ) -> CurrentWeather: ...

    async def get_daily_forecast(
        self, latitude: float, longitude: float, *, days: int = 7, units: Units = Units.METRIC
    ) -> list[DailyForecastDay]: ...
