"""Cache-aside, the same way for every service: read → on a miss load → store.

The service decides what is cached, under which key and for how long; this module only
knows how. The cache is optional: without one, or when it is down, `load` is simply called
every time.
"""

from collections.abc import Awaitable, Callable

import structlog
from pydantic import TypeAdapter, ValidationError

from app.core.cache.base import Cache, CacheUnavailableError

log = structlog.get_logger(__name__)


async def get_or_load[T](
    cache: Cache | None,
    key: str,
    ttl_seconds: int,
    adapter: TypeAdapter[T],
    load: Callable[[], Awaitable[T]],
) -> tuple[T, bool]:
    """Return (value, came_from_cache). `load` is only called on a cache miss.

    Values are stored as JSON through `adapter`. Errors from `load` (e.g. CityNotFoundError)
    propagate and are not cached.
    """
    raw = await _get(cache, key)
    if raw is not None:
        try:
            return adapter.validate_json(raw), True
        except ValidationError:
            # E.g. the model changed since the entry was written: treat it as a miss.
            log.warning("cache_entry_unreadable", key=key)

    value = await load()
    await _set(cache, key, adapter.dump_json(value).decode(), ttl_seconds)
    return value, False


async def _get(cache: Cache | None, key: str) -> str | None:
    if cache is None:
        return None
    try:
        return await cache.get(key)
    except CacheUnavailableError as exc:
        # Not fatal: the value is loaded instead.
        log.warning("cache_unavailable", operation="read", key=key, error=str(exc))
        return None


async def _set(cache: Cache | None, key: str, value: str, ttl_seconds: int) -> None:
    if cache is None:
        return
    try:
        await cache.set(key, value, ttl_seconds)
    except CacheUnavailableError as exc:
        log.warning("cache_unavailable", operation="write", key=key, error=str(exc))
