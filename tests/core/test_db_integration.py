from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import Database, get_database, get_session
from app.core.health import get_cache
from app.main import create_app, lifespan
from tests.conftest import TEST_DATABASE_URL
from tests.doubles import InMemoryCache
from tests.logs import json_logs

pytestmark = pytest.mark.postgres


async def test_ping(database: Database) -> None:
    assert await database.ping() is True


async def test_ping_with_a_wrong_password_returns_false() -> None:
    url = TEST_DATABASE_URL.replace("weather:weather@", "weather:wrong@")
    database = Database(Settings(_env_file=None, database_url=url))

    assert await database.ping() is False
    await database.dispose()


async def test_a_session_talks_to_the_test_database(database: Database) -> None:
    async with database.sessions() as session:
        name = await session.scalar(text("SELECT current_database()"))

    assert name == "weather_app_test"


@pytest.fixture
async def notes(database: Database) -> AsyncIterator[None]:
    """A throwaway table; the real tables come with Alembic (Phase 8.3)."""
    async with database.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE notes (body text NOT NULL)"))
    yield
    async with database.engine.begin() as connection:
        await connection.execute(text("DROP TABLE notes"))


@pytest.fixture
async def client(database: Database, notes: None) -> AsyncIterator[AsyncClient]:
    """An app with two routes that write through the `get_session` dependency."""
    app = FastAPI()
    app.dependency_overrides[get_database] = lambda: database

    @app.post("/committed")
    async def committed(session: Annotated[AsyncSession, Depends(get_session)]) -> None:
        async with session.begin():
            await session.execute(text("INSERT INTO notes VALUES ('kept')"))

    @app.post("/uncommitted")
    async def uncommitted(session: Annotated[AsyncSession, Depends(get_session)]) -> None:
        await session.execute(text("INSERT INTO notes VALUES ('lost')"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def note_bodies(database: Database) -> list[str]:
    async with database.sessions() as session:
        return list(await session.scalars(text("SELECT body FROM notes")))


async def test_a_committed_write_is_kept(client: AsyncClient, database: Database) -> None:
    await client.post("/committed")

    assert await note_bodies(database) == ["kept"]


async def test_an_uncommitted_write_is_rolled_back(client: AsyncClient, database: Database) -> None:
    await client.post("/uncommitted")

    assert await note_bodies(database) == []


async def test_ready_with_real_postgres(settings: Settings, database: Database) -> None:
    app = create_app(settings)
    app.dependency_overrides[get_cache] = InMemoryCache
    app.dependency_overrides[get_database] = lambda: database

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"redis": "ok", "postgres": "ok"}


async def test_lifespan_connects_to_postgres(settings: Settings, database: Database) -> None:
    """Real startup with a reachable Postgres: no warning, and readiness sees the database."""
    app = create_app(settings.model_copy(update={"database_url": TEST_DATABASE_URL}))

    with json_logs() as lines:
        async with lifespan(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health/ready")

    assert response.json()["checks"]["postgres"] == "ok"
    assert not [line for line in lines() if line["event"] == "postgres_unreachable"]
