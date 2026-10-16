from pydantic import BaseModel, Field


class Location(BaseModel):
    """A place resolved from the name the user typed."""

    name: str
    country: str | None = None
    country_code: str | None = Field(default=None, description="ISO-3166 alpha-2 code")
    region: str | None = Field(default=None, description="First-level region, e.g. a state")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str | None = None
