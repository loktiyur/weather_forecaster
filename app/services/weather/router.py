from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.services.weather.dependencies import WeatherServiceDep
from app.services.weather.errors import error_docs
from app.services.weather.queries import ForecastQuery, LocationSearchQuery, WeatherQuery
from app.services.weather.schemas import (
    CurrentWeatherResponse,
    ForecastResponse,
    LocationSearchResponse,
)

weather = APIRouter(prefix="/weather", tags=["weather"])
locations = APIRouter(prefix="/locations", tags=["locations"])


def cache_control(max_age_seconds: int) -> str:
    """Lets browsers and proxies reuse the response for as long as our own cache does."""
    return f"public, max-age={max_age_seconds}"


@weather.get(
    "/current",
    response_model=CurrentWeatherResponse,
    summary="Current weather for a city",
    responses=error_docs(404, 422, 501, 502, 504),
)
async def get_current_weather(
    query: Annotated[WeatherQuery, Query()], service: WeatherServiceDep, response: Response
) -> CurrentWeatherResponse:
    """Resolves the city name to a place and returns its current weather.

    The resolved `location` is part of the response, so the client can show
    *which* place was used for ambiguous names. `country` + `region` select one of
    several same-name places; `id` (from `/locations/search`) selects exactly one.
    """
    result = await service.get_current(
        query.city,
        location_id=query.id,
        country_code=query.country,
        region=query.region,
        language=query.lang,
        units=query.units,
    )
    response.headers["Cache-Control"] = cache_control(service.ttls.current)
    return result


@weather.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Daily forecast for a city",
    responses=error_docs(404, 422, 501, 502, 504),
)
async def get_forecast(
    query: Annotated[ForecastQuery, Query()], service: WeatherServiceDep, response: Response
) -> ForecastResponse:
    """Daily min/max temperature, humidity, sunrise and sunset for 1 to 16 days, starting today."""
    result = await service.get_forecast(
        query.city,
        location_id=query.id,
        country_code=query.country,
        region=query.region,
        language=query.lang,
        days=query.days,
        units=query.units,
    )
    response.headers["Cache-Control"] = cache_control(service.ttls.forecast)
    return result


@locations.get(
    "/search",
    response_model=LocationSearchResponse,
    summary="Find places matching a name",
    responses=error_docs(422, 502, 504),
)
async def search_locations(
    query: Annotated[LocationSearchQuery, Query()], service: WeatherServiceDep
) -> LocationSearchResponse:
    """Candidates for an ambiguous name (e.g. *Springfield*), best match first.

    Returns an empty `results` list, not 404, when nothing matches: an empty
    search result is a valid answer.
    """
    results = await service.search_locations(
        query.q, limit=query.limit, country_code=query.country, language=query.lang
    )
    return LocationSearchResponse(results=results)


# Included by main.py under /api/v1, in this order (it is the order in /docs).
router = APIRouter()
router.include_router(weather)
router.include_router(locations)
