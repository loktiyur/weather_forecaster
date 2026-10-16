from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    """Outgoing HTTP client used by the API clients; requests are intercepted by respx."""
    async with httpx.AsyncClient() as http_client:
        yield http_client
