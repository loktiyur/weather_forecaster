"""Test doubles for our own `Cache` interface. Real Redis is tested in tests/integration/."""

from dataclasses import dataclass, field

from app.cache.base import CacheUnavailableError


@dataclass
class InMemoryCache:
    """Stores values in a dict and remembers the TTL each key was written with."""

    values: dict[str, str] = field(default_factory=dict)
    ttls: dict[str, int] = field(default_factory=dict)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.values[key] = value
        self.ttls[key] = ttl_seconds

    async def ping(self) -> bool:
        return True


class UnavailableCache:
    """Behaves like a cache whose backend is down."""

    async def get(self, key: str) -> str | None:
        raise CacheUnavailableError("cache is down")

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        raise CacheUnavailableError("cache is down")

    async def ping(self) -> bool:
        return False
