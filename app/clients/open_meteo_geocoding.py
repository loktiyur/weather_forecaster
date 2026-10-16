import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.clients.base import GeocodingClient
from app.clients.http import get_json
from app.core.exceptions import UpstreamServiceError
from app.schemas.location import Location

SERVICE = "Open-Meteo Geocoding"


class _GeocodingResult(BaseModel):
    """One item of the `results` array, as returned by the API."""

    name: str
    latitude: float
    longitude: float
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None
    timezone: str | None = None


_results_adapter = TypeAdapter(list[_GeocodingResult])


class OpenMeteoGeocodingClient(GeocodingClient):
    """https://open-meteo.com/en/docs/geocoding-api: free, no API key."""

    def __init__(self, http: httpx.AsyncClient, url: str) -> None:
        self._http = http
        self._url = url

    async def search(
        self, name: str, *, count: int = 5, country_code: str | None = None
    ) -> list[Location]:
        params: dict[str, str | int] = {
            "name": name,
            "count": count,
            "language": "en",
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

        return [
            Location(
                name=r.name,
                country=r.country,
                country_code=r.country_code,
                region=r.admin1,
                latitude=r.latitude,
                longitude=r.longitude,
                timezone=r.timezone,
            )
            for r in results
        ]
