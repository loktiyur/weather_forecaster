import pytest
import respx
from httpx import AsyncClient

from tests.services.weather.api.upstream import mock_geocoding

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
