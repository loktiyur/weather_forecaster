"""Fixtures for tests that need real infrastructure (`@pytest.mark.integration`).

Locally the containers come from docker-compose.yml; in CI from GitHub Actions service
containers. If the infrastructure is not reachable the tests FAIL: a passing run always
means the code was really tested against Redis.
"""

import os
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
import redis.asyncio as redis
from redis.exceptions import RedisError

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")
DEV_REDIS_PORT = 6379


@pytest.fixture
async def redis_client() -> AsyncIterator[redis.Redis]:
    """A client for the test Redis, emptied before and after every test."""
    if urlparse(TEST_REDIS_URL).port == DEV_REDIS_PORT:
        pytest.fail(f"Refusing to flush {TEST_REDIS_URL}: that looks like the dev Redis")

    client = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True, socket_timeout=1)
    error: RedisError | None = None
    try:
        await client.ping()
    except RedisError as exc:
        error = exc
    if error is not None:
        # Outside the except block, so pytest prints only this message, not Redis's traceback.
        await client.aclose()
        pytest.fail(
            f"Test Redis at {TEST_REDIS_URL} is not reachable.\n"
            "Integration tests need the Docker container running:\n"
            "    docker compose up -d redis-test\n"
            "Run only the tests that need no Docker with: poetry run poe test-unit\n"
            f"(Redis error: {error})",
            pytrace=False,
        )

    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
