"""Request id and access log for every HTTP request."""

import re
import time
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
# An id from the caller (nginx sets one) is kept only if it looks like an id: it ends up in
# every log line, so arbitrary text must not get in there.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
# Docker and load balancers call these every few seconds. Successful calls are not logged;
# failing ones are, because then they are news.
QUIET_PATHS = frozenset({"/health", "/health/ready"})

access_log = structlog.get_logger("app.access")


class RequestContextMiddleware:
    """Gives each request an id (`X-Request-ID`, also in the response) and logs it once done.

    A plain ASGI middleware rather than `BaseHTTPMiddleware`: no extra task per request,
    and the id is set in the same context the route handlers run in.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        valid = incoming is not None and _VALID_REQUEST_ID.fullmatch(incoming)
        request_id = incoming if valid and incoming else uuid.uuid4().hex
        status_code = 500  # if the app fails before it starts a response
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        # Every log line written while this request is handled gets `request_id`.
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_with_request_id)
            finally:
                path = scope["path"]
                if path not in QUIET_PATHS or status_code >= 400:
                    query = scope["query_string"].decode("latin-1")
                    access_log.info(
                        "request",
                        method=scope["method"],
                        path=path,
                        query=query,
                        status=status_code,
                        duration_ms=round((time.perf_counter() - started) * 1000, 1),
                    )
