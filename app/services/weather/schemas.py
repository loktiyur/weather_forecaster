import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.language import Language


class Location(BaseModel):
    """A place resolved from the name the user typed."""

    id: int | None = Field(
        default=None,
        description="GeoNames id: stable and the same in every language. Pass it as `id` to "
        "the weather endpoints to get exactly this place",
        examples=[3067696],
    )
    name: str = Field(examples=["Prague"])
    country: str | None = Field(default=None, examples=["Czechia"])
    country_code: str | None = Field(
        default=None, description="ISO-3166 alpha-2 code", examples=["CZ"]
    )
    region: str | None = Field(
        default=None, description="First-level region, e.g. a state", examples=["Prague"]
    )
    latitude: float = Field(ge=-90, le=90, examples=[50.08804])
    longitude: float = Field(ge=-180, le=180, examples=[14.42076])
    timezone: str | None = Field(default=None, examples=["Europe/Prague"])


class LocationSearchResponse(BaseModel):
    """Wrapped in an object (not a bare list) so fields can be added without breaking clients."""

    results: list[Location]


class Units(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class CurrentWeather(BaseModel):
    time: dt.datetime = Field(description="Local time of the place", examples=["2026-10-16T14:15"])
    temperature: float = Field(examples=[16.0])
    apparent_temperature: float = Field(description="Feels-like temperature", examples=[15.2])
    relative_humidity: float = Field(description="Percent", examples=[60])
    wind_speed: float = Field(description="At 10 m above ground", examples=[2.6])
    weather_code: int = Field(description="WMO weather interpretation code", examples=[0])
    description: str = Field(examples=["Clear sky"])
    is_day: bool


class DailyForecastDay(BaseModel):
    date: dt.date = Field(examples=["2026-10-16"])
    temperature_max: float | None = Field(examples=[17.3])
    temperature_min: float | None = Field(examples=[4.9])
    relative_humidity_mean: float | None = Field(description="Percent", examples=[84])
    weather_code: int | None = Field(description="WMO weather interpretation code", examples=[45])
    description: str | None = Field(examples=["Fog"])
    sunrise: dt.datetime | None = Field(examples=["2026-10-16T07:25"])
    sunset: dt.datetime | None = Field(examples=["2026-10-16T18:09"])


class UnitLabels(BaseModel):
    """Tells the client how to display the numbers."""

    temperature: str = Field(examples=["°C"])
    wind_speed: str = Field(examples=["km/h"])

    @classmethod
    def for_units(cls, units: Units, language: Language = Language.EN) -> "UnitLabels":
        if units is Units.IMPERIAL:
            return cls(temperature="°F", wind_speed=_MPH.get(language, "mph"))
        return cls(temperature="°C", wind_speed=_KMH.get(language, "km/h"))


_KMH = {Language.UK: "км/год", Language.RU: "км/ч"}
_MPH = {Language.UK: "миль/год", Language.RU: "миль/ч"}


class CurrentWeatherResponse(BaseModel):
    location: Location
    current: CurrentWeather
    units: UnitLabels
    cached: bool = Field(description="True when the weather data came from the cache")


class ForecastResponse(BaseModel):
    location: Location
    daily: list[DailyForecastDay]
    units: UnitLabels
    cached: bool = Field(description="True when the weather data came from the cache")
