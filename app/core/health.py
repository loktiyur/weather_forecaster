import asyncio
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.cache.base import Cache
from app.core.db import Database, get_database

router = APIRouter(prefix="/health", tags=["health"])

CheckStatus = Literal["ok", "unavailable"]


def get_cache(request: Request) -> Cache:
    """The cache is created once in the app lifespan; tests replace it via dependency_overrides."""
    return cast(Cache, request.app.state.cache)


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    checks: dict[str, CheckStatus]


@router.get("", response_model=HealthResponse, summary="Liveness check")
async def health() -> HealthResponse:
    """The process is running. Does not look at dependencies."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is unreachable"}},
)
async def ready(
    cache: Annotated[Cache, Depends(get_cache)],
    database: Annotated[Database, Depends(get_database)],
) -> ReadinessResponse | JSONResponse:
    """Checks the dependencies. `503` if any is down.

    The weather endpoints still work without Redis (just slower), but a load balancer or
    an operator should know the cache is gone. Postgres holds the data the app keeps.
    """
    redis_ok, postgres_ok = await asyncio.gather(cache.ping(), database.ping())
    checks: dict[str, CheckStatus] = {
        "redis": _status(redis_ok),
        "postgres": _status(postgres_ok),
    }
    if all(result == "ok" for result in checks.values()):
        return ReadinessResponse(status="ready", checks=checks)
    body = ReadinessResponse(status="unavailable", checks=checks)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body.model_dump())


def _status(ok: bool) -> CheckStatus:
    return "ok" if ok else "unavailable"
