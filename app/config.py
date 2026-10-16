from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables and the `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"

    geocoding_provider: Literal["open_meteo", "geonames"] = "open_meteo"
    geonames_username: str | None = None

    open_meteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"

    http_timeout_seconds: float = 5.0

    @model_validator(mode="after")
    def _geonames_needs_username(self) -> Self:
        if self.geocoding_provider == "geonames" and not self.geonames_username:
            raise ValueError("GEONAMES_USERNAME is required when GEOCODING_PROVIDER=geonames")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
