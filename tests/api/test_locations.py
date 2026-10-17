import pytest
import respx
from httpx import AsyncClient

from tests.api.upstream import mock_geocoding

SEARCH = "/api/v1/locations/search"


async def test_search_returns_results(client: AsyncClient, respx_mock: respx.MockRouter) -> None:
    geocoding = mock_geocoding(respx_mock)

    response = await client.get(SEARCH, params={"q": "Prague", "limit": 3, "country": "cz"})

    assert response.status_code == 200
    [prague] = response.json()["results"]
    assert prague["name"] == "Prague"
    assert prague["timezone"] == "Europe/Prague"
    params = geocoding.calls.last.request.url.params
    assert params["count"] == "3"
    assert params["countryCode"] == "CZ"


async def test_search_defaults_to_5_results(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    geocoding = mock_geocoding(respx_mock)

    await client.get(SEARCH, params={"q": "Prague"})

    assert geocoding.calls.last.request.url.params["count"] == "5"


async def test_search_without_matches_returns_empty_list(
    client: AsyncClient, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock, "geocoding_not_found")

    response = await client.get(SEARCH, params={"q": "Qwertyuiopxyz"})

    assert response.status_code == 200
    assert response.json() == {"results": []}


@pytest.mark.parametrize(
    ("params", "field"),
    [({}, "q"), ({"q": "Prague", "limit": 0}, "limit"), ({"q": "Prague", "limit": 11}, "limit")],
)
async def test_search_validation(client: AsyncClient, params: dict[str, str], field: str) -> None:
    response = await client.get(SEARCH, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field
