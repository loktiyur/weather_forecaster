import pytest
import respx
from httpx import AsyncClient

from app.services.weather.cache_keys import CacheTtls
from tests.services.weather.api.upstream import PLACE_URL, mock_geocoding, mock_place

SEARCH = "/api/v1/locations/search"


async def test_search_returns_results(client: AsyncClient, respx_mock: respx.MockRouter) -> None:
    geocoding = mock_geocoding(respx_mock)

    response = await client.get(SEARCH, params={"q": "Prague", "limit": 3, "country": "cz"})

    assert response.status_code == 200
    [prague] = response.json()["results"]
    assert prague["name"] == "Prague"
    assert prague["timezone"] == "Europe/Prague"
    assert geocoding.calls.last.request.url.params["countryCode"] == "CZ"


async def test_search_defaults_to_5_results(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock, "geocoding_odessa")

    response = await client.get(SEARCH, params={"q": "Odessa"})

    assert len(response.json()["results"]) == 5


async def test_search_returns_only_populated_places(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock, "geocoding_odessa")  # 8 towns and "Odessa Dam"

    response = await client.get(SEARCH, params={"q": "Odessa", "limit": 20})

    names = [place["name"] for place in response.json()["results"]]
    assert len(names) == 8
    assert "Odessa Dam" not in names


async def test_search_without_matches_returns_empty_list(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock, "geocoding_not_found")

    response = await client.get(SEARCH, params={"q": "Qwertyuiopxyz"})

    assert response.status_code == 200
    assert response.json() == {"results": []}


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({}, "q"),
        ({"q": "12345"}, "q"),
        ({"q": "Prague", "limit": 0}, "limit"),
        ({"q": "Prague", "limit": 21}, "limit"),
    ],
)
async def test_search_validation(client: AsyncClient, params: dict[str, str], field: str) -> None:
    response = await client.get(SEARCH, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field


PLACE = "/api/v1/locations/{}"


async def test_get_location_by_id(client: AsyncClient, respx_mock: respx.MockRouter) -> None:
    place = mock_place(respx_mock, "place_kyiv_uk")

    response = await client.get(PLACE.format(703448), params={"lang": "uk"})

    assert response.status_code == 200
    assert response.json() == {
        "id": 703448,
        "name": "Київ",
        "country": "Україна",
        "country_code": "UA",
        "region": "Місто Київ",
        "latitude": 50.45466,
        "longitude": 30.5238,
        "timezone": "Europe/Kyiv",
    }
    assert place.calls.last.request.url.params["id"] == "703448"
    assert place.calls.last.request.url.params["language"] == "uk"
    assert response.headers["Cache-Control"] == f"public, max-age={CacheTtls().geocoding}"


async def test_get_location_defaults_to_english(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    place = mock_place(respx_mock, "place_kyiv_en")

    response = await client.get(PLACE.format(703448))

    assert response.json()["name"] == "Kyiv"
    assert place.calls.last.request.url.params["language"] == "en"


async def test_unknown_location_id_returns_404(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(PLACE_URL).respond(400, json={"error": True, "reason": "Location ID not found."})

    response = await client.get(PLACE.format(999999999))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LOCATION_NOT_FOUND"
    assert "Cache-Control" not in response.headers


@pytest.mark.parametrize(
    ("path", "params", "field"),
    [
        (PLACE.format(0), {}, "location_id"),
        (PLACE.format("abc"), {}, "location_id"),
        (PLACE.format(703448), {"lang": "de"}, "lang"),
    ],
)
async def test_get_location_validation(
    client: AsyncClient, path: str, params: dict[str, str], field: str
) -> None:
    response = await client.get(path, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field
