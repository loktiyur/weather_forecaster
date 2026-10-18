import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from pydantic import TypeAdapter, ValidationError

from app.cache import keys
from app.cache.base import Cache, CacheUnavailableError
from app.clients.base import GeocodingClient, WeatherClient
from app.config import Settings
from app.schemas.location import Location
from app.schemas.weather import (
    CurrentWeather,
    CurrentWeatherResponse,
    DailyForecastDay,
    ForecastResponse,
    UnitLabels,
    Units,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

_location_adapter = TypeAdapter(Location)
_current_adapter = TypeAdapter(CurrentWeather)
_daily_adapter = TypeAdapter(list[DailyForecastDay])


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


class WeatherService:
    """Business flow: resolve the city name to a place, then fetch its weather.

    Every lookup goes through the cache first (cache-aside). The cache is optional:
    without one, or when it is down, the clients are simply called every time.

    Knows nothing about HTTP requests/responses, so it can be reused (CLI, workers)
    and tested with fake clients.
    """

    def __init__(
        self,
        geocoding: GeocodingClient,
        weather: WeatherClient,
        cache: Cache | None = None,
        ttls: CacheTtls | None = None,
    ) -> None:
        self._geocoding = geocoding
        self._weather = weather
        self._cache = cache
        self.ttls = ttls or CacheTtls()

    async def get_current(
        self, city: str, *, country_code: str | None = None, units: Units = Units.METRIC
    ) -> CurrentWeatherResponse:
        location = await self._geocode(city, country_code)
        current, cached = await self._cached(
            keys.current_weather_key(location.latitude, location.longitude, units),
            self.ttls.current,
            _current_adapter,
            lambda: self._weather.get_current(location.latitude, location.longitude, units=units),
        )
        return CurrentWeatherResponse(
            location=location, current=current, units=UnitLabels.for_units(units), cached=cached
        )

    async def get_forecast(
        self,
        city: str,
        *,
        country_code: str | None = None,
        days: int = 7,
        units: Units = Units.METRIC,
    ) -> ForecastResponse:
        location = await self._geocode(city, country_code)
        daily, cached = await self._cached(
            keys.forecast_key(location.latitude, location.longitude, days, units),
            self.ttls.forecast,
            _daily_adapter,
            lambda: self._weather.get_daily_forecast(
                location.latitude, location.longitude, days=days, units=units
            ),
        )
        return ForecastResponse(
            location=location, daily=daily, units=UnitLabels.for_units(units), cached=cached
        )

    async def search_locations(
        self, query: str, *, limit: int = 5, country_code: str | None = None
    ) -> list[Location]:
        return await self._geocoding.search(query, count=limit, country_code=country_code)

    async def _geocode(self, city: str, country_code: str | None) -> Location:
        location, _ = await self._cached(
            keys.geocoding_key(city, country_code),
            self.ttls.geocoding,
            _location_adapter,
            lambda: self._geocoding.geocode(city, country_code=country_code),
        )
        return location

    async def _cached(
        self,
        key: str,
        ttl_seconds: int,
        adapter: TypeAdapter[T],
        load: Callable[[], Awaitable[T]],
    ) -> tuple[T, bool]:
        """Return (value, came_from_cache). `load` is only called on a cache miss.

        Errors from `load` (e.g. CityNotFoundError) propagate and are not cached.
        """
        raw = await self._cache_get(key)
        if raw is not None:
            try:
                return adapter.validate_json(raw), True
            except ValidationError:
                # E.g. the model changed since the entry was written: treat it as a miss.
                logger.warning("Ignoring unreadable cache entry %s", key)

        value = await load()
        await self._cache_set(key, adapter.dump_json(value).decode(), ttl_seconds)
        return value, False

    async def _cache_get(self, key: str) -> str | None:
        if self._cache is None:
            return None
        try:
            return await self._cache.get(key)
        except CacheUnavailableError as exc:
            logger.warning("Cache unavailable, calling the API instead: %s", exc)
            return None

    async def _cache_set(self, key: str, value: str, ttl_seconds: int) -> None:
        if self._cache is None:
            return
        try:
            await self._cache.set(key, value, ttl_seconds)
        except CacheUnavailableError as exc:
            logger.warning("Cache unavailable, result not stored: %s", exc)

    async def cache_is_reachable(self) -> bool:
        return self._cache is not None and await self._cache.ping()
