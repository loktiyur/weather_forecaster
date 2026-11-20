"""Test doubles for our own `Cache`, `Database` and `LocationStore`. Real Redis and Postgres
are tested by the integration tests."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.core.cache.base import CacheUnavailableError
from app.core.language import Language
from app.services.weather.repository import LocationStoreError
from app.services.weather.schemas import Location


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


@dataclass
class StubDatabase:
    """Stands in for `Database` where only readiness matters (the API tests use no SQL)."""

    reachable: bool = True

    async def ping(self) -> bool:
        return self.reachable


@dataclass
class InMemoryLocationStore:
    """Keeps places in a dict, per id and language, like the two tables do."""

    places: dict[tuple[int, Language], Location] = field(default_factory=dict)
    gets: list[tuple[int, Language]] = field(default_factory=list)

    async def get(self, location_id: int, language: Language) -> Location | None:
        self.gets.append((location_id, language))
        return self.places.get((location_id, language))

    async def save(self, locations: Iterable[Location], language: Language) -> None:
        for place in locations:
            if place.id is not None:
                self.places[place.id, language] = place


class UnavailableLocationStore:
    """Behaves like a location store whose database is down."""

    async def get(self, location_id: int, language: Language) -> Location | None:
        raise LocationStoreError("database is down")

    async def save(self, locations: Iterable[Location], language: Language) -> None:
        raise LocationStoreError("database is down")
