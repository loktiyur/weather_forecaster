import pytest
from pydantic import BaseModel, TypeAdapter

from app.core.cache.aside import get_or_load
from tests.doubles import InMemoryCache, UnavailableCache
from tests.logs import json_logs


class Point(BaseModel):
    x: int


ADAPTER = TypeAdapter(Point)


class Loader:
    """Counts how often the value had to be loaded (= cache misses)."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> Point:
        self.calls += 1
        return Point(x=1)


async def test_a_miss_loads_and_stores_with_the_ttl() -> None:
    cache, load = InMemoryCache(), Loader()

    value, cached = await get_or_load(cache, "point", 60, ADAPTER, load)

    assert (value, cached, load.calls) == (Point(x=1), False, 1)
    assert cache.values == {"point": '{"x":1}'}
    assert cache.ttls == {"point": 60}


async def test_a_hit_does_not_load() -> None:
    cache, load = InMemoryCache(values={"point": '{"x":2}'}), Loader()

    value, cached = await get_or_load(cache, "point", 60, ADAPTER, load)

    assert (value, cached, load.calls) == (Point(x=2), True, 0)


async def test_an_unreadable_entry_counts_as_a_miss() -> None:
    cache, load = InMemoryCache(values={"point": '{"y":"old format"}'}), Loader()

    with json_logs() as lines:
        value, cached = await get_or_load(cache, "point", 60, ADAPTER, load)

    assert (value, cached, load.calls) == (Point(x=1), False, 1)
    assert cache.values["point"] == '{"x":1}'  # overwritten in the current format
    [warning] = [line for line in lines() if line["event"] == "cache_entry_unreadable"]
    assert warning["key"] == "point"


async def test_a_cache_that_is_down_is_a_miss_on_read_and_write() -> None:
    load = Loader()

    with json_logs() as lines:
        value, cached = await get_or_load(UnavailableCache(), "point", 60, ADAPTER, load)

    assert (value, cached, load.calls) == (Point(x=1), False, 1)
    operations = [line["operation"] for line in lines() if line["event"] == "cache_unavailable"]
    assert operations == ["read", "write"]


async def test_without_a_cache_every_call_loads() -> None:
    load = Loader()

    await get_or_load(None, "point", 60, ADAPTER, load)
    await get_or_load(None, "point", 60, ADAPTER, load)

    assert load.calls == 2


async def test_a_failing_load_stores_nothing() -> None:
    cache = InMemoryCache()

    async def fail() -> Point:
        raise LookupError("not found")

    with pytest.raises(LookupError):
        await get_or_load(cache, "point", 60, ADAPTER, fail)
    assert cache.values == {}
