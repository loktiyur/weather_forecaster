import re
from collections.abc import Iterator
from typing import Any

import pytest
import respx
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.health import get_cache
from app.core.middleware import RequestContextMiddleware
from tests.doubles import UnavailableCache
from tests.logs import LogLines, json_logs
from tests.services.weather.api.upstream import mock_geocoding


@pytest.fixture
def logs(client: AsyncClient) -> Iterator[LogLines]:
    # After `client`: building the app configures logging, which this then redirects.
    with json_logs() as lines:
        yield lines


def access_lines(logs: LogLines) -> list[dict[str, Any]]:
    return [line for line in logs() if line["logger"] == "app.access"]


async def test_every_response_gets_a_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])


async def test_a_valid_incoming_id_is_kept(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "nginx-7f3a.1"})

    assert response.headers["X-Request-ID"] == "nginx-7f3a.1"


@pytest.mark.parametrize("bad", ["has spaces", "x" * 65, "new\nline", "<script>"])
async def test_an_invalid_incoming_id_is_replaced(client: AsyncClient, bad: str) -> None:
    response = await client.get("/health", headers={"X-Request-ID": bad})

    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])


async def test_requests_are_logged_with_their_id(client: AsyncClient, logs: LogLines) -> None:
    await client.get("/api/v1/weather/current", headers={"X-Request-ID": "trace-1"})

    [line] = access_lines(logs)
    assert line["event"] == "request"
    assert (line["method"], line["path"], line["status"]) == ("GET", "/api/v1/weather/current", 422)
    assert line["request_id"] == "trace-1"
    assert line["duration_ms"] >= 0
    assert structlog.contextvars.get_contextvars() == {}  # unbound after the request


async def test_the_query_string_is_logged(client: AsyncClient, logs: LogLines) -> None:
    await client.get("/api/v1/weather/current", params={"city": "1"})

    [line] = access_lines(logs)
    assert line["query"] == "city=1"
    assert line["path"] == "/api/v1/weather/current"


async def test_lines_written_during_a_request_carry_its_id(
    client: AsyncClient, logs: LogLines, respx_mock: respx.MockRouter
) -> None:
    mock_geocoding(respx_mock, "geocoding_not_found")

    await client.get("/api/v1/weather/current?city=Atlantis", headers={"X-Request-ID": "trace-2"})

    # The API's call to the geocoder is logged by httpx while the request is handled; the
    # test client's own httpx line (to http://test) is not part of any request.
    upstream = [line for line in logs() if "geocoding-api" in line["event"]]
    assert upstream and all(line["request_id"] == "trace-2" for line in upstream)
    client_line = next(line for line in logs() if "http://test" in line["event"])
    assert "request_id" not in client_line
    assert "message" not in client_line  # no duplicate of `event`


async def test_successful_health_checks_are_not_logged(client: AsyncClient, logs: LogLines) -> None:
    await client.get("/health")
    await client.get("/health/ready")

    assert access_lines(logs) == []


async def test_failing_health_checks_are_logged(
    app: FastAPI, client: AsyncClient, logs: LogLines
) -> None:
    app.dependency_overrides[get_cache] = UnavailableCache

    await client.get("/health/ready")

    [line] = access_lines(logs)
    assert line["status"] == 503


async def test_an_unhandled_error_is_logged_as_500(app: FastAPI, logs: LogLines) -> None:
    async def boom() -> None:
        raise RuntimeError("bug")

    app.add_api_route("/boom", boom)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    [line] = access_lines(logs)
    assert line["status"] == 500
    assert structlog.contextvars.get_contextvars() == {}


async def test_other_connection_types_pass_through_untouched() -> None:
    seen: list[str] = []

    async def inner(scope, receive, send):  # type: ignore[no-untyped-def]
        seen.append(scope["type"])

    await RequestContextMiddleware(inner)({"type": "lifespan"}, None, None)  # type: ignore[arg-type]

    assert seen == ["lifespan"]
