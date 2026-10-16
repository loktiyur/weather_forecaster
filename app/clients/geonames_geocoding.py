import asyncio
from typing import Any

from geopy import geocoders
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from pydantic import ValidationError

from app.clients.base import GeocodingClient
from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError
from app.schemas.location import Location

SERVICE = "GeoNames"


class GeoNamesGeocodingClient(GeocodingClient):
    """Alternative provider via geopy. Needs a free GeoNames username.

    geopy's client is synchronous, so each call runs in a worker thread
    (`asyncio.to_thread`) to keep the event loop free.
    """

    def __init__(self, geocoder: geocoders.GeoNames) -> None:
        self._geocoder = geocoder

    @classmethod
    def from_username(cls, username: str, timeout: float) -> "GeoNamesGeocodingClient":
        return cls(geocoders.GeoNames(username=username, timeout=timeout))

    async def search(
        self, name: str, *, count: int = 5, country_code: str | None = None
    ) -> list[Location]:
        # exactly_one=True makes geopy ask GeoNames for a single row instead of the default 100.
        exactly_one = count == 1
        try:
            found = await asyncio.to_thread(
                self._geocoder.geocode, name, exactly_one=exactly_one, country=country_code
            )
        except GeocoderTimedOut as exc:
            raise UpstreamTimeoutError(SERVICE) from exc
        except GeocoderServiceError as exc:
            # Also covers wrong username, quota exceeded, etc.
            raise UpstreamServiceError(SERVICE, str(exc)) from exc

        if not found:
            return []
        places = [found] if exactly_one else found[:count]
        return [self._to_location(place.raw) for place in places]

    @staticmethod
    def _to_location(raw: dict[str, Any]) -> Location:
        try:
            return Location(
                name=raw["name"],
                country=raw.get("countryName") or None,
                country_code=raw.get("countryCode") or None,
                region=raw.get("adminName1") or None,
                latitude=float(raw["lat"]),
                longitude=float(raw["lng"]),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise UpstreamServiceError(SERVICE, f"unexpected response format: {exc}") from exc
