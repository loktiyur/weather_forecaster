from app.clients.base import GeocodingClient, WeatherClient
from app.schemas.location import Location
from app.schemas.weather import CurrentWeatherResponse, ForecastResponse, UnitLabels, Units


class WeatherService:
    """Business flow: resolve the city name to a place, then fetch its weather.

    Knows nothing about HTTP requests/responses, so it can be reused (CLI, workers)
    and tested with fake clients.
    """

    def __init__(self, geocoding: GeocodingClient, weather: WeatherClient) -> None:
        self._geocoding = geocoding
        self._weather = weather

    async def get_current(
        self, city: str, *, country_code: str | None = None, units: Units = Units.METRIC
    ) -> CurrentWeatherResponse:
        location = await self._geocoding.geocode(city, country_code=country_code)
        current = await self._weather.get_current(
            location.latitude, location.longitude, units=units
        )
        return CurrentWeatherResponse(
            location=location, current=current, units=UnitLabels.for_units(units)
        )

    async def get_forecast(
        self,
        city: str,
        *,
        country_code: str | None = None,
        days: int = 7,
        units: Units = Units.METRIC,
    ) -> ForecastResponse:
        location = await self._geocoding.geocode(city, country_code=country_code)
        daily = await self._weather.get_daily_forecast(
            location.latitude, location.longitude, days=days, units=units
        )
        return ForecastResponse(location=location, daily=daily, units=UnitLabels.for_units(units))

    async def search_locations(
        self, query: str, *, limit: int = 5, country_code: str | None = None
    ) -> list[Location]:
        return await self._geocoding.search(query, count=limit, country_code=country_code)
