from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    """One shared client for the whole app, so connections are pooled and reused."""
    return httpx.AsyncClient(timeout=settings.http_timeout_seconds)


async def get_json(
    http: httpx.AsyncClient, url: str, params: dict[str, Any], *, service: str
) -> dict[str, Any]:
    """GET a JSON object and translate every transport/HTTP problem into a domain error."""
    try:
        response = await http.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise UpstreamTimeoutError(service) from exc
    except httpx.HTTPError as exc:
        raise UpstreamServiceError(service, f"request failed: {exc}") from exc

    if response.is_error:
        raise UpstreamServiceError(
            service, f"HTTP {response.status_code}: {_error_reason(response)}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamServiceError(service, "response is not valid JSON") from exc

    if not isinstance(data, dict):
        raise UpstreamServiceError(service, "expected a JSON object")
    return data


def _error_reason(response: httpx.Response) -> str:
    # Open-Meteo reports errors as {"error": true, "reason": "..."}
    try:
        reason = response.json().get("reason")
    except (ValueError, AttributeError):
        reason = None
    return str(reason) if reason else response.reason_phrase
