import httpx
import pytest
import respx

from app.clients.http import get_json
from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError

URL = "https://api.example.com/data"


async def test_returns_json_object(http: httpx.AsyncClient, respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))

    data = await get_json(http, URL, {"q": "x"}, service="Example")

    assert data == {"ok": True}
    assert route.calls.last.request.url.params["q"] == "x"


async def test_timeout_raises_upstream_timeout(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(UpstreamTimeoutError, match="Example"):
        await get_json(http, URL, {}, service="Example")


async def test_connection_error_raises_upstream_error(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("no route"))

    with pytest.raises(UpstreamServiceError, match="request failed"):
        await get_json(http, URL, {}, service="Example")


async def test_error_status_uses_open_meteo_reason(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(
        return_value=httpx.Response(400, json={"error": True, "reason": "Latitude out of range"})
    )

    with pytest.raises(UpstreamServiceError, match="HTTP 400: Latitude out of range"):
        await get_json(http, URL, {}, service="Example")


async def test_error_status_without_json_body_uses_reason_phrase(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(503, text="<html>down</html>"))

    with pytest.raises(UpstreamServiceError, match="HTTP 503: Service Unavailable"):
        await get_json(http, URL, {}, service="Example")


async def test_invalid_json_raises_upstream_error(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text="not json"))

    with pytest.raises(UpstreamServiceError, match="not valid JSON"):
        await get_json(http, URL, {}, service="Example")


async def test_non_object_json_raises_upstream_error(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json=[1, 2, 3]))

    with pytest.raises(UpstreamServiceError, match="expected a JSON object"):
        await get_json(http, URL, {}, service="Example")
