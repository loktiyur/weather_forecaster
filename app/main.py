from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.errors import register_exception_handlers
from app.api.routes import health, locations, weather
from app.clients.factory import create_geocoding_client
from app.clients.http import create_http_client
from app.clients.open_meteo_weather import OpenMeteoWeatherClient
from app.config import Settings, get_settings
from app.services.weather_service import WeatherService

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
    async with create_http_client(settings) as http:
        app.state.weather_service = WeatherService(
            geocoding=create_geocoding_client(settings, http),
            weather=OpenMeteoWeatherClient(http, settings.open_meteo_forecast_url),
        )
        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Weather Forecaster",
        description="Current weather and daily forecast for a city.",
        version="0.2.0",
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
