import asyncio
from typing import Any

from geopy import geocoders
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from pydantic import ValidationError

from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError
from app.core.language import Language
from app.services.weather.errors import NotSupportedError
from app.services.weather.providers.base import GeocodingClient, SearchResult
from app.services.weather.schemas import Location

SERVICE = "GeoNames"


class GeoNamesGeocodingClient(GeocodingClient):
    """Alternative provider via geopy. Needs a free GeoNames username.

    geopy's client is synchronous, so each call runs in a worker thread
    (`asyncio.to_thread`) to keep the event loop free.

    Limits of geopy's GeoNames client: no `language` (names come in GeoNames' default
    language) and no lookup by id (`get` raises `NotSupportedError`, answered with 501).
    """

    def __init__(self, geocoder: geocoders.GeoNames) -> None:
        self._geocoder = geocoder

    @classmethod
    def from_username(cls, username: str, timeout: float) -> "GeoNamesGeocodingClient":
        return cls(geocoders.GeoNames(username=username, timeout=timeout))

    async def find(
        self, name: str, *, count: int, country_code: str | None, language: Language
    ) -> SearchResult:
        # All candidates (GeoNames' default of 100 rows): the first one may be a country or a
        # region, which is filtered out below, so asking for a single row is not enough.
        try:
            found = await asyncio.to_thread(
                self._geocoder.geocode, name, exactly_one=False, country=country_code
            )
        except GeocoderTimedOut as exc:
            raise UpstreamTimeoutError(SERVICE) from exc
        except GeocoderServiceError as exc:
            # Also covers wrong username, quota exceeded, etc.
            raise UpstreamServiceError(SERVICE, str(exc)) from exc

        if not found:
            return SearchResult([])
        best = found[0].raw
        country = best.get("name") if str(best.get("fcode", "")).startswith("PCL") else None
        # Feature class P = populated place (A would be a country or region, H water, ...).
        places = [place for place in found if place.raw.get("fcl", "P") == "P"][:count]
        return SearchResult([self._to_location(place.raw) for place in places], country=country)

    async def get(self, place_id: int, *, language: Language) -> Location | None:
        raise NotSupportedError(SERVICE, "looking places up by id")

    @staticmethod
    def _to_location(raw: dict[str, Any]) -> Location:
        try:
            return Location(
                id=raw.get("geonameId"),
                name=raw["name"],
                country=raw.get("countryName") or None,
                country_code=raw.get("countryCode") or None,
                region=raw.get("adminName1") or None,
                latitude=float(raw["lat"]),
                longitude=float(raw["lng"]),
            )
        except (KeyError, ValueError, ValidationError) as exc:
            raise UpstreamServiceError(SERVICE, f"unexpected response format: {exc}") from exc
