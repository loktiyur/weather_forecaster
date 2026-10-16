import httpx
import pytest
import respx

from app.clients.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.config import Settings
from app.core.exceptions import CityNotFoundError, UpstreamServiceError
from tests.fixtures import load_fixture

URL = Settings.model_fields["open_meteo_geocoding_url"].default


@pytest.fixture
def geocoding(http: httpx.AsyncClient) -> OpenMeteoGeocodingClient:
    return OpenMeteoGeocodingClient(http, URL)


async def test_search_maps_results_to_locations(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("geocoding_prague"))
    )

    [prague] = await geocoding.search("Prague", count=1)

    assert prague.name == "Prague"
    assert prague.country == "Czechia"
    assert prague.country_code == "CZ"
    assert prague.region == "Prague"
    assert prague.latitude == pytest.approx(50.08804)
    assert prague.longitude == pytest.approx(14.42076)
    assert prague.timezone == "Europe/Prague"


async def test_search_sends_expected_params(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("geocoding_prague"))
    )

    await geocoding.search("Prague", count=3, country_code="cz")

    params = route.calls.last.request.url.params
    assert params["name"] == "Prague"
    assert params["count"] == "3"
    assert params["countryCode"] == "CZ"
    assert params["language"] == "en"


async def test_search_without_country_does_not_send_country_code(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("geocoding_prague"))
    )

    await geocoding.search("Prague")

    assert "countryCode" not in route.calls.last.request.url.params


async def test_search_returns_empty_list_when_nothing_found(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("geocoding_not_found"))
    )

    assert await geocoding.search("Qwertyuiopxyz") == []


async def test_geocode_returns_best_match(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("geocoding_prague"))
    )

    location = await geocoding.geocode("Prague")

    assert location.name == "Prague"
    assert route.calls.last.request.url.params["count"] == "1"


async def test_geocode_raises_city_not_found(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("geocoding_not_found"))
    )

    with pytest.raises(CityNotFoundError) as exc_info:
        await geocoding.geocode("Qwertyuiopxyz")
    assert exc_info.value.city == "Qwertyuiopxyz"


async def test_malformed_result_raises_upstream_error(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json={"results": [{"name": "Prague"}]})
    )

    with pytest.raises(UpstreamServiceError, match="unexpected response format"):
        await geocoding.search("Prague")
