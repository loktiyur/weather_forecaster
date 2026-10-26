from dataclasses import dataclass, field
from typing import Any

import pytest
from geopy.exc import GeocoderAuthenticationFailure, GeocoderTimedOut

from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError
from app.core.language import Language
from app.services.weather.errors import NotACityError, NotSupportedError
from app.services.weather.providers.geonames_geocoding import GeoNamesGeocodingClient

PRAGUE_RAW = {
    "name": "Prague",
    "countryName": "Czechia",
    "countryCode": "CZ",
    "adminName1": "Prague",
    "lat": "50.08804",
    "lng": "14.42076",
}
PRAGUE_OKLAHOMA_RAW = {
    "name": "Prague",
    "countryName": "United States",
    "countryCode": "US",
    "adminName1": "Oklahoma",
    "lat": "35.48674",
    "lng": "-96.68502",
}


@dataclass
class FakePlace:
    raw: dict[str, Any]


@dataclass
class FakeGeoNames:
    """Stands in for geopy's GeoNames, which makes real (synchronous) HTTP calls."""

    result: Any = None
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def geocode(self, query: str, **kwargs: Any) -> Any:
        self.calls.append({"query": query, **kwargs})
        if self.error:
            raise self.error
        return self.result


async def test_geocode_returns_the_best_match() -> None:
    fake = FakeGeoNames(result=[FakePlace(PRAGUE_RAW), FakePlace(PRAGUE_OKLAHOMA_RAW)])
    client = GeoNamesGeocodingClient(fake)

    location = await client.geocode("Prague", country_code="CZ")

    assert fake.calls == [{"query": "Prague", "exactly_one": False, "country": "CZ"}]
    assert location.name == "Prague"
    assert location.country == "Czechia"
    assert location.country_code == "CZ"
    assert location.region == "Prague"
    assert location.latitude == pytest.approx(50.08804)
    assert location.longitude == pytest.approx(14.42076)
    assert location.timezone is None


async def test_multiple_results_are_limited_to_count() -> None:
    places = [FakePlace(PRAGUE_RAW), FakePlace(PRAGUE_OKLAHOMA_RAW), FakePlace(PRAGUE_RAW)]
    fake = FakeGeoNames(result=places)
    client = GeoNamesGeocodingClient(fake)

    results = await client.search("Prague", count=2)

    assert fake.calls[0]["exactly_one"] is False
    assert [r.country_code for r in results] == ["CZ", "US"]


async def test_only_populated_places_are_returned_and_a_country_is_reported() -> None:
    country = {**PRAGUE_RAW, "name": "Czechia", "fcl": "A", "fcode": "PCLI"}
    city = {**PRAGUE_RAW, "fcl": "P", "fcode": "PPLC"}
    client = GeoNamesGeocodingClient(FakeGeoNames(result=[FakePlace(country), FakePlace(city)]))

    found = await client.find("Czechia", count=1, country_code=None, language=Language.EN)

    assert [p.name for p in found.places] == ["Prague"]
    assert found.country == "Czechia"
    with pytest.raises(NotACityError):
        await client.geocode("Czechia")


async def test_no_result_returns_empty_list() -> None:
    client = GeoNamesGeocodingClient(FakeGeoNames(result=None))

    assert await client.search("Qwertyuiopxyz") == []


async def test_timeout_raises_upstream_timeout() -> None:
    fake = FakeGeoNames(error=GeocoderTimedOut("slow"))
    client = GeoNamesGeocodingClient(fake)

    with pytest.raises(UpstreamTimeoutError, match="GeoNames"):
        await client.search("Prague")


async def test_service_error_raises_upstream_error() -> None:
    fake = FakeGeoNames(error=GeocoderAuthenticationFailure("user does not exist"))
    client = GeoNamesGeocodingClient(fake)

    with pytest.raises(UpstreamServiceError, match="user does not exist"):
        await client.search("Prague")


async def test_malformed_raw_raises_upstream_error() -> None:
    fake = FakeGeoNames(result=[FakePlace({"name": "Prague", "lat": "not-a-number", "lng": "1"})])
    client = GeoNamesGeocodingClient(fake)

    with pytest.raises(UpstreamServiceError, match="unexpected response format"):
        await client.search("Prague", count=1)


async def test_ids_come_from_geonames() -> None:
    client = GeoNamesGeocodingClient(
        FakeGeoNames(result=[FakePlace({**PRAGUE_RAW, "geonameId": 3067696})])
    )

    [prague] = await client.search("Prague")

    assert prague.id == 3067696


async def test_lookup_by_id_is_not_supported() -> None:
    client = GeoNamesGeocodingClient(FakeGeoNames())

    with pytest.raises(
        NotSupportedError, match="GeoNames does not support looking places up by id"
    ):
        await client.get(3067696, language=Language.EN)
