import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.clients.base import GeocodingClient, SearchResult
from app.clients.http import get_json
from app.core.exceptions import UpstreamServiceError
from app.schemas.language import Language
from app.schemas.location import Location

SERVICE = "Open-Meteo Geocoding"

# The most results the API returns. Entries that are not populated places are dropped after
# the call, so the client asks for all candidates and cuts the list to `count` afterwards.
API_MAX_RESULTS = 100


class _GeocodingResult(BaseModel):
    """One place, as returned by the API (an item of `results`, or the /get response)."""

    id: int | None = None
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None
    timezone: str | None = None
    # GeoNames feature code: PPL, PPLA, PPLC, ... for populated places; PCLI is a country.
    feature_code: str | None = None

    @property
    def is_country(self) -> bool:
        # PCLI (independent), PCLD (dependent), PCLS, PCLF, ...: all political entities.
        return self.feature_code is not None and self.feature_code.startswith("PCL")

    @property
    def is_populated_place(self) -> bool:
        # A missing code is kept: better a place too many than none when the field is absent.
        return self.feature_code is None or self.feature_code.startswith("PPL")

    def to_location(self) -> Location:
        return Location(
            id=self.id,
            name=self.name,
            country=self.country,
            country_code=self.country_code,
            region=self.admin1,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
        )


_results_adapter = TypeAdapter(list[_GeocodingResult])


class OpenMeteoGeocodingClient(GeocodingClient):
    """https://open-meteo.com/en/docs/geocoding-api: free, no API key."""

    def __init__(self, http: httpx.AsyncClient, url: str, place_url: str) -> None:
        self._http = http
        self._url = url
        self._place_url = place_url

    async def find(
        self, name: str, *, count: int, country_code: str | None, language: Language
    ) -> SearchResult:
        params: dict[str, str | int] = {
            "name": name,
            "count": API_MAX_RESULTS,
            # Searches the names in this language (Cyrillic names need uk / ru) and returns
            # names, regions and countries in it.
            "language": language.value,
            "format": "json",
        }
        if country_code:
            params["countryCode"] = country_code.upper()

        data = await get_json(self._http, self._url, params, service=SERVICE)

        # The API omits "results" entirely when nothing matches.
        try:
            results = _results_adapter.validate_python(data.get("results", []))
        except ValidationError as exc:
            raise UpstreamServiceError(SERVICE, f"unexpected response format: {exc}") from exc

        country = results[0].name if results and results[0].is_country else None
        places = [r.to_location() for r in results if r.is_populated_place][:count]
        return SearchResult(places, country=country)

    async def get(self, place_id: int, *, language: Language) -> Location | None:
        params = {"id": place_id, "language": language.value}
        try:
            data = await get_json(self._http, self._place_url, params, service=SERVICE)
        except UpstreamServiceError as exc:
            # An unknown id is answered with HTTP 400 {"reason": "Location ID not found."}
            if "Location ID not found" in exc.detail:
                return None
            raise
        try:
            result = _GeocodingResult.model_validate(data)
        except ValidationError as exc:
            raise UpstreamServiceError(SERVICE, f"unexpected response format: {exc}") from exc
        # Ids also exist for countries, continents, dams, ...: the same rule as for search.
        return result.to_location() if result.is_populated_place else None
