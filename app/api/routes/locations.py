from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import WeatherServiceDep
from app.api.errors import error_docs
from app.api.queries import LocationSearchQuery
from app.schemas.location import LocationSearchResponse

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get(
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
    results = await service.search_locations(query.q, limit=query.limit, country_code=query.country)
    return LocationSearchResponse(results=results)
