import datetime as dt
from enum import StrEnum

from pydantic import BaseModel


class Units(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class CurrentWeather(BaseModel):
    time: dt.datetime
    temperature: float
    apparent_temperature: float
    relative_humidity: float
    wind_speed: float
    weather_code: int
    description: str
    is_day: bool


class DailyForecastDay(BaseModel):
    date: dt.date
    temperature_max: float | None
    temperature_min: float | None
    relative_humidity_mean: float | None
    weather_code: int | None
    description: str | None
    sunrise: dt.datetime | None
    sunset: dt.datetime | None
