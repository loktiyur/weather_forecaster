import asyncio
import json

import pytest
import redis.asyncio as redis

from app.core.cache.redis import RedisCache

pytestmark = pytest.mark.integration


@pytest.fixture
def cache(redis_client: redis.Redis) -> RedisCache:
    return RedisCache(redis_client)


async def test_ping(cache: RedisCache) -> None:
    assert await cache.ping() is True


async def test_missing_key_returns_none(cache: RedisCache) -> None:
    assert await cache.get("does-not-exist") is None


async def test_set_then_get_round_trips_json(cache: RedisCache) -> None:
    value = json.dumps({"temperature": 16.0, "unit": "°C", "name": "Kyjev / Київ"})

    await cache.set("weather:test", value, ttl_seconds=60)

    stored = await cache.get("weather:test")
    assert stored == value
    assert json.loads(stored)["unit"] == "°C"


async def test_set_writes_the_ttl(cache: RedisCache, redis_client: redis.Redis) -> None:
    await cache.set("weather:test", "x", ttl_seconds=600)

    assert 595 <= await redis_client.ttl("weather:test") <= 600


async def test_value_expires_after_ttl(cache: RedisCache) -> None:
    await cache.set("weather:short", "x", ttl_seconds=1)
    assert await cache.get("weather:short") == "x"

    await asyncio.sleep(1.2)

    assert await cache.get("weather:short") is None


async def test_set_overwrites_value_and_ttl(cache: RedisCache, redis_client: redis.Redis) -> None:
    await cache.set("weather:test", "old", ttl_seconds=10)
    await cache.set("weather:test", "new", ttl_seconds=600)

    assert await cache.get("weather:test") == "new"
    assert await redis_client.ttl("weather:test") > 10
