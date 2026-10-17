from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import WeatherServiceDep
from app.api.errors import error_docs
from app.api.queries import ForecastQuery, WeatherQuery
from app.schemas.weather import CurrentWeatherResponse, ForecastResponse

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get(
    "/current",
    response_model=CurrentWeatherResponse,
    summary="Current weather for a city",
    responses=error_docs(404, 422, 502, 504),
)
async def get_current_weather(
    query: Annotated[WeatherQuery, Query()], service: WeatherServiceDep
) -> CurrentWeatherResponse:
    """Resolves the city name to a place and returns its current weather.

    The resolved `location` is part of the response, so the client can show
    *which* place was used for ambiguous names.
    """
    return await service.get_current(query.city, country_code=query.country, units=query.units)


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Daily forecast for a city",
    responses=error_docs(404, 422, 502, 504),
)
async def get_forecast(
    query: Annotated[ForecastQuery, Query()], service: WeatherServiceDep
) -> ForecastResponse:
    """Daily min/max temperature, humidity, sunrise and sunset for 1 to 16 days, starting today."""
    return await service.get_forecast(
        query.city, country_code=query.country, days=query.days, units=query.units
    )
