from pydantic import BaseModel, Field


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
