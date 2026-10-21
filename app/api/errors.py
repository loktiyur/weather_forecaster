"""Map exceptions to HTTP responses that all share the `ErrorResponse` format."""

from collections.abc import Mapping
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    CityNotFoundError,
    LocationNotFoundError,
    NotACityError,
    NotSupportedError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.schemas.errors import ErrorBody, ErrorResponse, FieldError

log = structlog.get_logger(__name__)

HTTP_ERROR_CODES = {
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[FieldError] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        headers=headers,
    )


async def _city_not_found(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, CityNotFoundError)
    return error_response(status.HTTP_404_NOT_FOUND, "CITY_NOT_FOUND", str(exc))


async def _not_a_city(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NotACityError)
    return error_response(status.HTTP_404_NOT_FOUND, "NOT_A_CITY", str(exc))


async def _location_not_found(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, LocationNotFoundError)
    return error_response(status.HTTP_404_NOT_FOUND, "LOCATION_NOT_FOUND", str(exc))


async def _not_supported(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NotSupportedError)
    return error_response(status.HTTP_501_NOT_IMPLEMENTED, "NOT_SUPPORTED", str(exc))


async def _upstream_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, UpstreamServiceError)
    # The real cause goes to the logs; the client gets a message without internal details.
    log.warning("upstream_error", service=exc.service, detail=exc.detail)
    return error_response(
        status.HTTP_502_BAD_GATEWAY,
        "UPSTREAM_ERROR",
        "The weather provider returned an error. Please try again later.",
    )


async def _upstream_timeout(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, UpstreamTimeoutError)
    log.warning("upstream_timeout", service=exc.service)
    return error_response(
        status.HTTP_504_GATEWAY_TIMEOUT,
        "UPSTREAM_TIMEOUT",
        "The weather provider did not respond in time. Please try again later.",
    )


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [_field_error(err) for err in exc.errors()]
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Invalid request parameters.",
        details=details,
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    # Unknown routes, wrong methods, ... use the same format instead of FastAPI's {"detail": ...}
    assert isinstance(exc, StarletteHTTPException)
    return error_response(
        exc.status_code,
        HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR"),
        str(exc.detail),
        headers=exc.headers,
    )


def _field_error(error: Any) -> FieldError:
    # loc looks like ("query", "city"); a missing model-level field has only ("query",)
    loc = [str(part) for part in error.get("loc", ())]
    return FieldError(
        location=loc[0] if loc else "request",
        field=".".join(loc[1:]) or "-",
        message=str(error.get("msg", "Invalid value")),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CityNotFoundError, _city_not_found)
    app.add_exception_handler(NotACityError, _not_a_city)
    app.add_exception_handler(LocationNotFoundError, _location_not_found)
    app.add_exception_handler(NotSupportedError, _not_supported)
    app.add_exception_handler(UpstreamTimeoutError, _upstream_timeout)
    app.add_exception_handler(UpstreamServiceError, _upstream_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)


def error_docs(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """`responses=` entries for OpenAPI, so /docs shows the error format per endpoint."""
    descriptions = {
        404: "No place found for the name (`CITY_NOT_FOUND`) or the id "
        "(`LOCATION_NOT_FOUND`), or the name is a country (`NOT_A_CITY`)",
        422: "Invalid query parameters",
        501: "The configured geocoding provider cannot do this, e.g. look places up by id",
        502: "The upstream weather/geocoding provider failed",
        504: "The upstream provider did not respond in time",
    }
    return {code: {"model": ErrorResponse, "description": descriptions[code]} for code in statuses}
