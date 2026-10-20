import httpx
import pytest
import respx

from app.clients.open_meteo_geocoding import OpenMeteoGeocodingClient
from app.config import Settings
from app.core.exceptions import CityNotFoundError, NotACityError, UpstreamServiceError
from app.schemas.language import Language
from tests.fixtures import load_fixture

URL = Settings.model_fields["open_meteo_geocoding_url"].default
PLACE_URL = Settings.model_fields["open_meteo_place_url"].default


@pytest.fixture
def geocoding(http: httpx.AsyncClient) -> OpenMeteoGeocodingClient:
    return OpenMeteoGeocodingClient(http, URL, PLACE_URL)


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
    assert params["count"] == "100"  # all candidates; cut to `count` after filtering
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
    assert route.calls.last.request.url.params["name"] == "Prague"


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


def _result(name: str, feature_code: str | None) -> dict[str, object]:
    return {"name": name, "latitude": 51.5, "longitude": 10.5, "feature_code": feature_code}


async def test_only_populated_places_are_returned(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    # "Germany" finds the country first (PCLI), then a town called Germany in Georgia, US.
    results = [
        _result("Germany", "PCLI"),
        _result("Odessa Dam", "DAM"),
        _result("Germany", "PPL"),
        _result("Berlin", "PPLC"),
        _result("Somewhere", None),
    ]
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json={"results": results}))

    places = await geocoding.search("Germany", count=2)

    assert [p.name for p in places] == ["Germany", "Berlin"]
    assert len(await geocoding.search("Germany", count=10)) == 3  # missing code is kept


async def test_a_country_name_is_reported(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    # "Poland" finds the country first, then Terryville, CT (once called Poland) and towns.
    results = [_result("Poland", "PCLI"), _result("Terryville", "PPL"), _result("Poland", "PPL")]
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json={"results": results}))

    found = await geocoding.find("Poland", count=5, country_code=None, language=Language.EN)

    assert found.country == "Poland"
    assert [p.name for p in found.places] == ["Terryville", "Poland"]
    with pytest.raises(NotACityError) as exc_info:
        await geocoding.geocode("poland")
    assert (exc_info.value.name, exc_info.value.country) == ("poland", "Poland")


async def test_a_country_further_down_is_not_reported(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    results = [_result("Georgia", "PPL"), _result("Georgia", "PCLI")]
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json={"results": results}))

    assert (
        await geocoding.find("Georgia", count=5, country_code=None, language=Language.EN)
    ).country is None


async def test_search_sends_the_language(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(200, json=load_fixture("geocoding_kyiv_uk"))
    )

    [kyiv, *_] = await geocoding.search("Київ", language=Language.UK)

    assert route.calls.last.request.url.params["language"] == "uk"
    assert (kyiv.id, kyiv.name, kyiv.country) == (703448, "Київ", "Україна")


async def test_get_returns_the_place_in_the_language(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(PLACE_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("place_kyiv_en"))
    )

    place = await geocoding.get(703448, language=Language.EN)

    assert place is not None
    assert (place.id, place.name, place.region) == (703448, "Kyiv", "Kyiv City")
    assert dict(route.calls.last.request.url.params) == {"id": "703448", "language": "en"}


async def test_get_unknown_id_returns_none(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(PLACE_URL).respond(400, json={"error": True, "reason": "Location ID not found."})

    assert await geocoding.get(999999999, language=Language.EN) is None


async def test_get_id_of_something_that_is_not_a_place_returns_none(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    europe = {
        "id": 6255148,
        "name": "Europe",
        "latitude": 48.7,
        "longitude": 9.1,
        "feature_code": "CONT",
    }
    respx_mock.get(PLACE_URL).respond(200, json=europe)

    assert await geocoding.get(6255148, language=Language.EN) is None


async def test_get_other_upstream_errors_are_raised(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(PLACE_URL).respond(503, json={"error": True, "reason": "Overloaded"})

    with pytest.raises(UpstreamServiceError, match="Overloaded"):
        await geocoding.get(703448, language=Language.EN)


async def test_get_malformed_place_raises_upstream_error(
    geocoding: OpenMeteoGeocodingClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(PLACE_URL).respond(200, json={"id": 1, "name": "No coordinates"})

    with pytest.raises(UpstreamServiceError, match="unexpected response format"):
        await geocoding.get(1, language=Language.EN)
