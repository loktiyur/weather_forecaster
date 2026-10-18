import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.errors import register_exception_handlers
from app.api.routes import health, locations, weather
from app.cache.redis_cache import RedisCache, create_redis_client
from app.clients.factory import create_geocoding_client
from app.clients.http import create_http_client
from app.clients.open_meteo_weather import OpenMeteoWeatherClient
from app.config import Settings, get_settings
from app.services.weather_service import CacheTtls, WeatherService

logger = logging.getLogger(__name__)

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
        logger.warning("Redis at %s is unreachable; running without cache", settings.redis_url)

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


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Weather Forecaster",
        description="Current weather and daily forecast for a city.",
        version="0.3.0",
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )
    app.state.settings = settings or get_settings()

    register_exception_handlers(app)

    api_v1 = APIRouter(prefix=API_V1_PREFIX)
    api_v1.include_router(weather.router)
    api_v1.include_router(locations.router)
    app.include_router(api_v1)
    app.include_router(health.router)
    return app


app = create_app()
