import httpx
import pytest
import respx

from app.clients import http as http_module
from app.clients.http import MAX_ATTEMPTS, get_json
from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError
from tests.logs import json_logs

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


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_temporary_error_is_retried_and_then_succeeds(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter, status: int
) -> None:
    route = respx_mock.get(URL).mock(
        side_effect=[
            httpx.Response(status, json={"error": True, "reason": "Overloaded"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )

    with json_logs() as lines:
        assert await get_json(http, URL, {}, service="Example") == {"ok": True}

    assert route.call_count == 2
    [retry] = [line for line in lines() if line["event"] == "upstream_retry"]
    assert retry["level"] == "warning"
    assert (retry["service"], retry["status"]) == ("Example", status)
    assert (retry["attempt"], retry["max_attempts"]) == (2, 3)


async def test_gives_up_after_the_last_attempt(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(503, json={"error": True, "reason": "Overloaded"})
    )

    with pytest.raises(UpstreamServiceError, match="HTTP 503: Overloaded"):
        await get_json(http, URL, {}, service="Example")
    assert route.call_count == MAX_ATTEMPTS


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ReadTimeout("slow"), UpstreamTimeoutError),
        (httpx.ConnectError("no route"), UpstreamServiceError),
    ],
)
async def test_transport_errors_are_retried(
    http: httpx.AsyncClient,
    respx_mock: respx.MockRouter,
    error: Exception,
    expected: type[Exception],
) -> None:
    route = respx_mock.get(URL).mock(side_effect=error)

    with pytest.raises(expected):
        await get_json(http, URL, {}, service="Example")
    assert route.call_count == MAX_ATTEMPTS


async def test_a_dropped_connection_is_retried(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).mock(
        side_effect=[httpx.ReadError("reset"), httpx.Response(200, json={"ok": True})]
    )

    with json_logs() as lines:
        assert await get_json(http, URL, {}, service="Example") == {"ok": True}

    assert route.call_count == 2
    [retry] = [line for line in lines() if line["event"] == "upstream_retry"]
    assert retry["error"] == "ReadError"  # no HTTP status: the kind of failure instead
    assert "status" not in retry


@pytest.mark.parametrize("status", [400, 404])
async def test_client_errors_are_not_retried(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter, status: int
) -> None:
    route = respx_mock.get(URL).mock(
        return_value=httpx.Response(
            status, json={"error": True, "reason": "Location ID not found."}
        )
    )

    with pytest.raises(UpstreamServiceError, match="Location ID not found"):
        await get_json(http, URL, {}, service="Example")
    assert route.call_count == 1


async def test_time_budget_stops_retrying(
    http: httpx.AsyncClient, respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(http_module, "RETRY_BUDGET_SECONDS", 0)
    route = respx_mock.get(URL).mock(return_value=httpx.Response(503))

    with pytest.raises(UpstreamServiceError):
        await get_json(http, URL, {}, service="Example")
    assert route.call_count == 1  # the budget was used up by the first attempt
