from pydantic import TypeAdapter

from app.core.cache.aside import get_or_load
from app.core.cache.base import Cache
from app.core.language import Language
from app.services.weather import cache_keys
from app.services.weather.cache_keys import CacheTtls
from app.services.weather.errors import LocationNotFoundError
from app.services.weather.providers.base import GeocodingClient, WeatherClient
from app.services.weather.schemas import (
    CurrentWeather,
    CurrentWeatherResponse,
    DailyForecastDay,
    ForecastResponse,
    Location,
    UnitLabels,
    Units,
)
from app.services.weather.weather_codes import describe_weather_code

_location_adapter = TypeAdapter(Location)
_current_adapter = TypeAdapter(CurrentWeather)
_daily_adapter = TypeAdapter(list[DailyForecastDay])


class WeatherService:
    """Business flow: resolve the city name to a place, then fetch its weather.

    Every lookup goes through the cache first (cache-aside with `core/cache`'s
    `get_or_load`). The service decides what is cached, under which key and for how long
    (`cache_keys.py`); without a cache, or when it is down, the clients are simply called.

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
        self,
        city: str | None = None,
        *,
        location_id: int | None = None,
        country_code: str | None = None,
        region: str | None = None,
        language: Language = Language.EN,
        units: Units = Units.METRIC,
    ) -> CurrentWeatherResponse:
        location = await self._locate(city, location_id, country_code, region, language)
        current, cached = await get_or_load(
            self._cache,
            cache_keys.current_weather_key(location.latitude, location.longitude, units),
            self.ttls.current,
            _current_adapter,
            lambda: self._weather.get_current(location.latitude, location.longitude, units=units),
        )
        # The cached weather has no language; only the text shown to people is translated.
        current = current.model_copy(
            update={"description": describe_weather_code(current.weather_code, language)}
        )
        return CurrentWeatherResponse(
            location=location,
            current=current,
            units=UnitLabels.for_units(units, language),
            cached=cached,
        )

    async def get_forecast(
        self,
        city: str | None = None,
        *,
        location_id: int | None = None,
        country_code: str | None = None,
        region: str | None = None,
        language: Language = Language.EN,
        days: int = 7,
        units: Units = Units.METRIC,
    ) -> ForecastResponse:
        location = await self._locate(city, location_id, country_code, region, language)
        daily, cached = await get_or_load(
            self._cache,
            cache_keys.forecast_key(location.latitude, location.longitude, days, units),
            self.ttls.forecast,
            _daily_adapter,
            lambda: self._weather.get_daily_forecast(
                location.latitude, location.longitude, days=days, units=units
            ),
        )
        daily = [
            day.model_copy(
                update={
                    "description": None
                    if day.weather_code is None
                    else describe_weather_code(day.weather_code, language)
                }
            )
            for day in daily
        ]
        return ForecastResponse(
            location=location,
            daily=daily,
            units=UnitLabels.for_units(units, language),
            cached=cached,
        )

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 5,
        country_code: str | None = None,
        language: Language = Language.EN,
    ) -> list[Location]:
        return await self._geocoding.search(
            query, count=limit, country_code=country_code, language=language
        )

    async def _locate(
        self,
        city: str | None,
        location_id: int | None,
        country_code: str | None,
        region: str | None,
        language: Language,
    ) -> Location:
        """The place to show: by id when given (exact, any language), otherwise by name."""
        if location_id is not None:
            return await self._place(location_id, language)
        if city is None:
            raise ValueError("either city or location_id is required")
        return await self._geocode(city, country_code, region, language)

    async def _geocode(
        self, city: str, country_code: str | None, region: str | None, language: Language
    ) -> Location:
        location, _ = await get_or_load(
            self._cache,
            cache_keys.geocoding_key(city, country_code, region, language),
            self.ttls.geocoding,
            _location_adapter,
            lambda: self._geocoding.geocode(
                city, country_code=country_code, region=region, language=language
            ),
        )
        return location

    async def _place(self, location_id: int, language: Language) -> Location:
        async def load() -> Location:
            place = await self._geocoding.get(location_id, language=language)
            if place is None:
                raise LocationNotFoundError(location_id)
            return place

        location, _ = await get_or_load(
            self._cache,
            cache_keys.place_key(location_id, language),
            self.ttls.geocoding,
            _location_adapter,
            load,
        )
        return location
