"""Runs the migrations (`alembic upgrade`, `alembic check`, ...) on the async engine."""

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.db import Base

# Import every service's models here, so `alembic check` and autogenerate see their tables.
# (None yet: the first table comes in Phase 8.4.)

# One schema per service (ARCHITECTURE.md §8.2). Autogenerate compares only these, never
# `public` or anything else in the database.
SERVICE_SCHEMAS = {"weather"}

config = context.config

# Only from the alembic CLI: tests pass a Config without a file and keep their own logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def database_url() -> str:
    """Tests set the URL on the Config; everywhere else it is DATABASE_URL, as for the app."""
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    return name in SERVICE_SCHEMAS if type_ == "schema" else True


def configure(**kwargs: Any) -> None:
    context.configure(
        target_metadata=Base.metadata,
        include_schemas=True,
        include_name=include_name,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """`alembic upgrade --sql`: prints the SQL instead of running it."""
    configure(url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # NullPool: a one-off command needs one connection, not a pool that outlives it.
    engine = create_async_engine(database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
