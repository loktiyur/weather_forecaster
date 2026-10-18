import pytest

from app.cache.base import CacheUnavailableError
from app.cache.keys import current_weather_key, forecast_key, geocoding_key
from app.cache.redis_cache import RedisCache, create_redis_client
from app.config import Settings
from app.schemas.weather import Units
from tests.conftest import UNREACHABLE_REDIS_URL


def test_geocoding_key_is_normalised() -> None:
    assert geocoding_key("  Prague ", None) == "geo:prague:"
    assert geocoding_key("PRAGUE", "cz") == "geo:prague:CZ"


def test_weather_keys_round_coordinates() -> None:
    assert current_weather_key(50.08804, 14.42076, Units.METRIC) == (
        "weather:current:50.09:14.42:metric"
    )
    assert forecast_key(50.08804, 14.42076, 3, Units.IMPERIAL) == (
        "weather:forecast:50.09:14.42:3:imperial"
    )


@pytest.fixture
def unreachable_cache() -> RedisCache:
    settings = Settings(_env_file=None, redis_url=UNREACHABLE_REDIS_URL, redis_timeout_seconds=0.2)
    return RedisCache(create_redis_client(settings))


async def test_get_on_unreachable_redis_raises_cache_unavailable(
    unreachable_cache: RedisCache,
) -> None:
    with pytest.raises(CacheUnavailableError, match="GET failed"):
        await unreachable_cache.get("key")


async def test_set_on_unreachable_redis_raises_cache_unavailable(
    unreachable_cache: RedisCache,
) -> None:
    with pytest.raises(CacheUnavailableError, match="SET failed"):
        await unreachable_cache.set("key", "value", ttl_seconds=10)


async def test_ping_on_unreachable_redis_returns_false(unreachable_cache: RedisCache) -> None:
    assert await unreachable_cache.ping() is False


def test_redis_client_uses_settings() -> None:
    settings = Settings(_env_file=None, redis_url="redis://cache:6390/2", redis_timeout_seconds=0.3)

    kwargs = create_redis_client(settings).connection_pool.connection_kwargs

    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("cache", 6390, 2)
    assert kwargs["socket_timeout"] == 0.3
    assert kwargs["decode_responses"] is True
