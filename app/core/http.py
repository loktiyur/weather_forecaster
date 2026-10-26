from collections.abc import Callable
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)
from tenacity.wait import wait_base

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError

log = structlog.get_logger(__name__)

# Retries for failures that are usually over a moment later (Open-Meteo answering
# 503 "overloaded", a dropped connection). Few attempts, so an overloaded service is not
# flooded, and a time budget, so a user never waits for three full timeouts.
MAX_ATTEMPTS = 3
RETRY_BUDGET_SECONDS = 8.0
# 5xx: the provider's fault; 429: too many requests. Other 4xx ("Location ID not found",
# a bad parameter) would fail the same way again, so they are never retried.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# ~0.2 s, then ~0.4 s, plus up to 0.2 s of random jitter so clients do not retry in step.
# A module attribute, so tests can replace it with `wait_none()`.
RETRY_WAIT: wait_base = wait_exponential_jitter(initial=0.2, max=1.0, jitter=0.2)


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    """One shared client for the whole app, so connections are pooled and reused."""
    return httpx.AsyncClient(timeout=settings.http_timeout_seconds)


def _is_temporary(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRY_STATUSES
    # Timeouts and connection problems (TimeoutException is a TransportError too).
    return isinstance(exc, httpx.TransportError)


def _log_retry(service: str) -> Callable[[RetryCallState], None]:
    def log_retry(state: RetryCallState) -> None:
        exc = state.outcome.exception() if state.outcome else None
        # The HTTP status when there was an answer, otherwise the kind of failure.
        reason = (
            {"status": exc.response.status_code}
            if isinstance(exc, httpx.HTTPStatusError)
            else {"error": type(exc).__name__}
        )
        log.warning(
            "upstream_retry",
            service=service,
            attempt=state.attempt_number + 1,
            max_attempts=MAX_ATTEMPTS,
            **reason,
        )

    return log_retry


async def get_json(
    http: httpx.AsyncClient, url: str, params: dict[str, Any], *, service: str
) -> dict[str, Any]:
    """GET a JSON object and translate every transport/HTTP problem into a domain error.

    Temporary failures are retried (see `RETRY_STATUSES`); the error raised after the last
    attempt is the same as without retries.
    """
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_temporary),
            stop=stop_after_attempt(MAX_ATTEMPTS) | stop_after_delay(RETRY_BUDGET_SECONDS),
            wait=RETRY_WAIT,
            before_sleep=_log_retry(service),
            reraise=True,
        ):
            with attempt:
                response = await http.get(url, params=params)
                if response.status_code in RETRY_STATUSES:
                    response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise UpstreamTimeoutError(service) from exc
    except httpx.HTTPStatusError as exc:
        response = exc.response  # still failing after the last attempt: reported below
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
