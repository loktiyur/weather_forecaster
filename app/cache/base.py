from typing import Protocol


class CacheUnavailableError(Exception):
    """The cache backend could not be reached or failed. Callers treat it as a cache miss."""


class Cache(Protocol):
    """Key-value store with expiry. Values are strings (JSON); callers own the serialisation."""

    async def get(self, key: str) -> str | None:
        """Return the stored value, or None if the key is missing or expired."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store the value; it expires after `ttl_seconds`."""
        ...

    async def ping(self) -> bool:
        """True if the backend is reachable. Never raises."""
        ...
