"""Query parameter models. FastAPI reads each model's fields from the query string."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.language import Language
from app.services.weather.providers.base import MAX_SEARCH_RESULTS
from app.services.weather.schemas import Units

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

    @field_validator("city", "q", check_fields=False)
    @classmethod
    def _require_letter(cls, value: str | None) -> str | None:
        # The geocoder also matches postal codes ("10001" → New York, "123" → whatever postcode
        # starts with it). This API looks places up by name only, so a name needs a letter.
        if value is not None and not any(char.isalpha() for char in value):
            raise ValueError("must contain at least one letter")
        return value


Lang = Annotated[
    Language,
    Field(description="Language of place names, weather descriptions and unit labels"),
]


class WeatherQuery(_QueryModel):
    city: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="City name (not a postal code). Required unless `id` is given",
        examples=["Prague"],
    )
    id: int | None = Field(
        default=None,
        ge=1,
        description="`location.id` of a place (e.g. from `/locations/search`): selects exactly "
        "that place in any language; `city`, `country` and `region` are then ignored",
        examples=[3067696],
    )
    country: CountryCode = None
    region: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="First-level region (state, province, ...) as returned by "
        "`/locations/search`; picks one of several same-name places in a country",
        examples=["Texas"],
    )
    lang: Lang = Language.EN
    units: Units = Field(
        default=Units.METRIC, description="`metric` (°C, km/h) or `imperial` (°F, mph)"
    )

    @model_validator(mode="after")
    def _city_or_id(self) -> Self:
        if self.city is None and self.id is None:
            raise ValueError("either `city` or `id` is required")
        return self


class ForecastQuery(WeatherQuery):
    days: int = Field(default=7, ge=1, le=16, description="Number of days, including today")


class LocationSearchQuery(_QueryModel):
    q: str = Field(
        min_length=1,
        max_length=100,
        description="Place name (not a postal code)",
        examples=["Springfield"],
    )
    country: CountryCode = None
    lang: Lang = Language.EN
    limit: int = Field(
        default=5, ge=1, le=MAX_SEARCH_RESULTS, description="Maximum number of results"
    )
