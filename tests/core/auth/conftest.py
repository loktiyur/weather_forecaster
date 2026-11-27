"""Shared by the auth tests: an app on the real test Postgres and a client for it."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.db import Database, get_database
from app.main import create_app

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/me"
PREFERENCES = "/api/v1/me/preferences"
ANNA = {"email": "anna@example.com", "password": "correct horse"}


@pytest.fixture
def app(settings: Settings, clean_database: Database) -> FastAPI:
    application = create_app(settings)
    application.dependency_overrides[get_database] = lambda: clean_database
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # https: the cookie is Secure, so a client on http:// would never send it back.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


@pytest.fixture
async def logged_in(client: AsyncClient) -> AsyncClient:
    """The client after registering Anna, so it carries her login cookie."""
    response = await client.post(REGISTER, json=ANNA)
    assert response.status_code == 201
    return client
