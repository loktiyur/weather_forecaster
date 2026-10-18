import redis.asyncio as redis
from redis.exceptions import RedisError

from app.cache.base import CacheUnavailableError
from app.config import Settings


def create_redis_client(settings: Settings) -> redis.Redis:
    """No connection is opened here; redis-py connects lazily on the first command.

    So the app starts even when Redis is down, and recovers once it is back.
    """
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=settings.redis_timeout_seconds,
        socket_connect_timeout=settings.redis_timeout_seconds,
    )


class RedisCache:
    """`Cache` implementation on Redis. Every Redis problem becomes `CacheUnavailableError`."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        try:
            value = await self._client.get(key)
        except RedisError as exc:
            raise CacheUnavailableError(f"Redis GET failed: {exc}") from exc
        return value if value is None else str(value)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            # SET with EX: value and expiry are written in one atomic command.
            await self._client.set(key, value, ex=ttl_seconds)
        except RedisError as exc:
            raise CacheUnavailableError(f"Redis SET failed: {exc}") from exc

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except RedisError:
            return False
