"""Query parameter models. FastAPI reads each model's fields from the query string."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.weather import Units

CountryCode = Annotated[
    str | None,
    Field(
        pattern=r"^[A-Za-z]{2}$",
        description="ISO-3166 alpha-2 country code to pick the right place, "
        "e.g. `US` for Paris, Texas",
        examples=["CZ"],
    ),
]


class _QueryModel(BaseModel):
    # "  Prague " → "Prague"; a value of only spaces then fails min_length.
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("country", check_fields=False)
    @classmethod
    def _upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class WeatherQuery(_QueryModel):
    city: str = Field(min_length=1, max_length=100, description="City name", examples=["Prague"])
    country: CountryCode = None
    units: Units = Field(
        default=Units.METRIC, description="`metric` (°C, km/h) or `imperial` (°F, mph)"
    )


class ForecastQuery(WeatherQuery):
    days: int = Field(default=7, ge=1, le=16, description="Number of days, including today")


class LocationSearchQuery(_QueryModel):
    q: str = Field(min_length=1, max_length=100, description="Place name", examples=["Springfield"])
    country: CountryCode = None
    limit: int = Field(default=5, ge=1, le=10, description="Maximum number of results")
