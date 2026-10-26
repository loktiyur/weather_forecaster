"""The weather service's own errors and how they map to HTTP responses."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core import errors
from app.core.errors import error_response
from app.core.exceptions import WeatherForecasterError


class CityNotFoundError(WeatherForecasterError):
    def __init__(self, city: str) -> None:
        self.city = city
        super().__init__(f"No place found for '{city}'.")


class NotACityError(WeatherForecasterError):
    """The name is a country ("Germany"): there is no single place to show the weather for."""

    def __init__(self, name: str, country: str) -> None:
        self.name = name
        self.country = country
        super().__init__(f"'{country}' is a country, not a city.")


class LocationNotFoundError(WeatherForecasterError):
    """No populated place has this id."""

    def __init__(self, location_id: int) -> None:
        self.location_id = location_id
        super().__init__(f"No place found with id {location_id}.")


class NotSupportedError(WeatherForecasterError):
    """The configured provider cannot do this (e.g. GeoNames via geopy: lookup by id)."""

    def __init__(self, service: str, feature: str) -> None:
        self.service = service
        self.feature = feature
        super().__init__(f"{service} does not support {feature}.")


ERROR_DESCRIPTIONS = {
    404: "No place found for the name (`CITY_NOT_FOUND`) or the id "
    "(`LOCATION_NOT_FOUND`), or the name is a country (`NOT_A_CITY`)",
    501: "The configured geocoding provider cannot do this, e.g. look places up by id",
}


def error_docs(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return errors.error_docs(*statuses, descriptions=ERROR_DESCRIPTIONS)


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


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CityNotFoundError, _city_not_found)
    app.add_exception_handler(NotACityError, _not_a_city)
    app.add_exception_handler(LocationNotFoundError, _location_not_found)
    app.add_exception_handler(NotSupportedError, _not_supported)
