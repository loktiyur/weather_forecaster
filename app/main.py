from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import structlog
from fastapi import APIRouter, FastAPI

from app.api.errors import register_exception_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.routes import health, locations, weather
from app.cache.redis_cache import RedisCache, create_redis_client
from app.clients.factory import create_geocoding_client
from app.clients.http import create_http_client
from app.clients.open_meteo_weather import OpenMeteoWeatherClient
from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.services.weather_service import CacheTtls, WeatherService

log = structlog.get_logger(__name__)

API_V1_PREFIX = "/api/v1"

TAGS_METADATA = [
    {"name": "weather", "description": "Current weather and daily forecast for a city."},
    {"name": "locations", "description": "Resolve and disambiguate place names."},
    {"name": "health", "description": "Service status checks."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create long-lived resources on startup and close them on shutdown."""
    settings: Settings = app.state.settings
    redis_client = create_redis_client(settings)
    cache = RedisCache(redis_client)
    if not await cache.ping():
        # Not fatal: the app works without the cache and reconnects when Redis is back.
        log.warning("redis_unreachable", redis=_without_credentials(settings.redis_url))

    async with create_http_client(settings) as http:
        app.state.weather_service = WeatherService(
            geocoding=create_geocoding_client(settings, http),
            weather=OpenMeteoWeatherClient(http, settings.open_meteo_forecast_url),
            cache=cache,
            ttls=CacheTtls.from_settings(settings),
        )
        try:
            yield
        finally:
            await redis_client.aclose()


def _without_credentials(url: str) -> str:
    """`redis://:secret@host:6379/0` → `redis://host:6379/0`: passwords stay out of logs."""
    parts = urlsplit(url)
    return parts._replace(netloc=parts.netloc.rpartition("@")[2]).geturl()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Before uvicorn logs "Started server process": it imports the app first.
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title="Weather Forecaster",
        description="Current weather and daily forecast for a city.",
        version="1.1.1",  # x-release-please-version (release-please bumps it)
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )
    app.state.settings = settings

    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    api_v1 = APIRouter(prefix=API_V1_PREFIX)
    api_v1.include_router(weather.router)
    api_v1.include_router(locations.router)
    app.include_router(api_v1)
    app.include_router(health.router)
    return app


app = create_app()
