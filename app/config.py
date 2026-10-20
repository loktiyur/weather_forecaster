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
    open_meteo_place_url: str = "https://geocoding-api.open-meteo.com/v1/get"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"

    http_timeout_seconds: float = 5.0

    redis_url: str = "redis://localhost:6379/0"
    # Short timeouts: if Redis hangs, requests fall back to the APIs instead of waiting.
    redis_timeout_seconds: float = 0.5

    cache_ttl_geocoding_seconds: int = 7 * 24 * 3600
    cache_ttl_current_seconds: int = 600
    cache_ttl_forecast_seconds: int = 3600

    @model_validator(mode="after")
    def _geonames_needs_username(self) -> Self:
        if self.geocoding_provider == "geonames" and not self.geonames_username:
            raise ValueError("GEONAMES_USERNAME is required when GEOCODING_PROVIDER=geonames")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
