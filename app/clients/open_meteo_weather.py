import datetime as dt
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.clients.http import get_json
from app.core.exceptions import UpstreamServiceError
from app.core.weather_codes import describe_weather_code
from app.schemas.weather import CurrentWeather, DailyForecastDay, Units

SERVICE = "Open-Meteo Forecast"

CURRENT_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "weather_code",
    "wind_speed_10m",
]
DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "sunrise",
    "sunset",
]
MAX_FORECAST_DAYS = 16


class _CurrentBlock(BaseModel):
    time: dt.datetime
    temperature_2m: float
    relative_humidity_2m: float
    apparent_temperature: float
    is_day: int
    weather_code: int
    wind_speed_10m: float


class _DailyBlock(BaseModel):
    """Open-Meteo returns daily data column-wise: one list per variable."""

    time: list[dt.date]
    weather_code: list[int | None]
    temperature_2m_max: list[float | None]
    temperature_2m_min: list[float | None]
    relative_humidity_2m_mean: list[float | None]
    sunrise: list[dt.datetime | None]
    sunset: list[dt.datetime | None]


class OpenMeteoWeatherClient:
    """https://open-meteo.com/en/docs: free, no API key."""

    def __init__(self, http: httpx.AsyncClient, url: str) -> None:
        self._http = http
        self._url = url

    async def get_current(
        self, latitude: float, longitude: float, *, units: Units = Units.METRIC
    ) -> CurrentWeather:
        params = self._base_params(latitude, longitude, units)
        params["current"] = ",".join(CURRENT_VARIABLES)

        data = await get_json(self._http, self._url, params, service=SERVICE)
        try:
            current = _CurrentBlock.model_validate(data.get("current"))
        except ValidationError as exc:
            raise UpstreamServiceError(SERVICE, f"unexpected 'current' block: {exc}") from exc

        return CurrentWeather(
            time=current.time,
            temperature=current.temperature_2m,
            apparent_temperature=current.apparent_temperature,
            relative_humidity=current.relative_humidity_2m,
            wind_speed=current.wind_speed_10m,
            weather_code=current.weather_code,
            description=describe_weather_code(current.weather_code),
            is_day=bool(current.is_day),
        )

    async def get_daily_forecast(
        self, latitude: float, longitude: float, *, days: int = 7, units: Units = Units.METRIC
    ) -> list[DailyForecastDay]:
        if not 1 <= days <= MAX_FORECAST_DAYS:
            raise ValueError(f"days must be between 1 and {MAX_FORECAST_DAYS}")

        params = self._base_params(latitude, longitude, units)
        params["daily"] = ",".join(DAILY_VARIABLES)
        params["forecast_days"] = days

        data = await get_json(self._http, self._url, params, service=SERVICE)
        try:
            daily = _DailyBlock.model_validate(data.get("daily"))
            # Turn the columns into one row per day; strict=True catches columns of unequal length.
            rows = zip(
                daily.time,
                daily.weather_code,
                daily.temperature_2m_max,
                daily.temperature_2m_min,
                daily.relative_humidity_2m_mean,
                daily.sunrise,
                daily.sunset,
                strict=True,
            )
            return [
                DailyForecastDay(
                    date=date,
                    weather_code=code,
                    description=describe_weather_code(code) if code is not None else None,
                    temperature_max=t_max,
                    temperature_min=t_min,
                    relative_humidity_mean=humidity,
                    sunrise=sunrise,
                    sunset=sunset,
                )
                for date, code, t_max, t_min, humidity, sunrise, sunset in rows
            ]
        except (ValidationError, ValueError) as exc:
            raise UpstreamServiceError(SERVICE, f"unexpected 'daily' block: {exc}") from exc

    @staticmethod
    def _base_params(latitude: float, longitude: float, units: Units) -> dict[str, Any]:
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            # Times are returned in the local time of the place.
            "timezone": "auto",
        }
        if units is Units.IMPERIAL:
            params["temperature_unit"] = "fahrenheit"
            params["wind_speed_unit"] = "mph"
        return params
