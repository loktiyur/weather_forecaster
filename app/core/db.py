"""PostgreSQL through SQLAlchemy 2.0 async (asyncpg): the engine, sessions and the model `Base`."""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import MetaData, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings

# Fixed names for constraints and indexes, so Alembic (Phase 8.3) generates the same names on
# every machine and a migration can drop a constraint by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class of all SQLAlchemy models. Each service puts its tables in its own schema."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    """The engine (a connection pool) and the session factory, created once per process.

    No connection is opened here; the pool connects on first use. So the app starts even
    when Postgres is down, and recovers once it is back.
    """

    def __init__(self, settings: Settings) -> None:
        self._timeout = settings.database_timeout_seconds
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            # Checks a pooled connection before handing it out, so a Postgres restart costs
            # one reconnect instead of one failed request per stale connection.
            pool_pre_ping=True,
            connect_args={"timeout": self._timeout},
        )
        # expire_on_commit=False: objects stay readable after commit. Reloading them would
        # be a hidden query, which async SQLAlchemy cannot do on attribute access.
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ping(self) -> bool:
        try:
            async with asyncio.timeout(self._timeout), self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):  # OSError: refused or timed out (TimeoutError)
            return False
        return True

    async def dispose(self) -> None:
        """Closes the pooled connections (on shutdown)."""
        await self.engine.dispose()


def get_database(request: Request) -> Database:
    """Created once in the app lifespan; tests replace it via dependency_overrides."""
    return cast(Database, request.app.state.database)


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    """One session per request, closed when the request ends.

    The session does not commit by itself: code that writes commits explicitly
    (`async with session.begin(): ...`), and anything left uncommitted is rolled back on close.
    """
    async with database.sessions() as session:
        yield session
