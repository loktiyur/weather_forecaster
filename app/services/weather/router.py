from typing import Annotated

from fastapi import APIRouter, Path, Query, Response

from app.core.auth.router import UserLoader, UserLoaderDep
from app.core.auth.schemas import Preferences
from app.core.units import Units
from app.services.weather.dependencies import WeatherServiceDep
from app.services.weather.errors import error_docs
from app.services.weather.queries import (
    ForecastQuery,
    LocationQuery,
    LocationSearchQuery,
    WeatherQuery,
)
from app.services.weather.schemas import (
    CurrentWeatherResponse,
    ForecastResponse,
    Location,
    LocationSearchResponse,
)

weather = APIRouter(prefix="/weather", tags=["weather"])
locations = APIRouter(prefix="/locations", tags=["locations"])


def cache_control(max_age_seconds: int, *, personal: bool = False) -> str:
    """Lets browsers and proxies reuse the response for as long as our own cache does.

    `personal`: the answer depends on who is logged in, so only the user's own browser may
    keep it, never a shared proxy.
    """
    return f"{'private' if personal else 'public'}, max-age={max_age_seconds}"


async def resolve_units(requested: Units | None, load_user: UserLoader) -> tuple[Units, bool]:
    """The units to answer in, and whether they depend on the caller (a personal answer).

    `units` in the URL wins and is the same for everyone. Without it: the logged-in user's
    saved units, otherwise metric. Only then is the user loaded from the database.
    """
    if requested is not None:
        return requested, False
    user = await load_user()
    saved = Preferences.model_validate(user.preferences).units if user else None
    return saved or Units.METRIC, True


@weather.get(
    "/current",
    response_model=CurrentWeatherResponse,
    summary="Current weather for a city",
    responses=error_docs(404, 422, 501, 502, 504),
)
async def get_current_weather(
    query: Annotated[WeatherQuery, Query()],
    service: WeatherServiceDep,
    load_user: UserLoaderDep,
    response: Response,
) -> CurrentWeatherResponse:
    """Resolves the city name to a place and returns its current weather.

    The resolved `location` is part of the response, so the client can show
    *which* place was used for ambiguous names. `country` + `region` select one of
    several same-name places; `id` (from `/locations/search`) selects exactly one.
    """
    units, personal = await resolve_units(query.units, load_user)
    result = await service.get_current(
        query.city,
        location_id=query.id,
        country_code=query.country,
        region=query.region,
        language=query.lang,
        units=units,
    )
    response.headers["Cache-Control"] = cache_control(service.ttls.current, personal=personal)
    return result


@weather.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Daily forecast for a city",
    responses=error_docs(404, 422, 501, 502, 504),
)
async def get_forecast(
    query: Annotated[ForecastQuery, Query()],
    service: WeatherServiceDep,
    load_user: UserLoaderDep,
    response: Response,
) -> ForecastResponse:
    """Daily min/max temperature, humidity, sunrise and sunset for 1 to 16 days, starting today."""
    units, personal = await resolve_units(query.units, load_user)
    result = await service.get_forecast(
        query.city,
        location_id=query.id,
        country_code=query.country,
        region=query.region,
        language=query.lang,
        days=query.days,
        units=units,
    )
    response.headers["Cache-Control"] = cache_control(service.ttls.forecast, personal=personal)
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


# After /search: a path is matched in the order the routes were added, so "search" never
# reaches this route as an id.
@locations.get(
    "/{location_id}",
    response_model=Location,
    summary="A place by its id",
    responses=error_docs(404, 422, 501, 502, 504),
)
async def get_location(
    location_id: Annotated[
        int,
        Path(
            ge=1,
            description="`location.id` from any other endpoint (the GeoNames id)",
            examples=[3067696],
        ),
    ],
    query: Annotated[LocationQuery, Query()],
    service: WeatherServiceDep,
    response: Response,
) -> Location:
    """One place, with its names in `lang`.

    Places seen before are served from the database; others are looked up at the provider
    once and stored. 404 `LOCATION_NOT_FOUND` when no populated place has this id.
    """
    result = await service.get_location(location_id, language=query.lang)
    response.headers["Cache-Control"] = cache_control(service.ttls.geocoding)
    return result


# Included by main.py under /api/v1, in this order (it is the order in /docs).
router = APIRouter()
router.include_router(weather)
router.include_router(locations)
