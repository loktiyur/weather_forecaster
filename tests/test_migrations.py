"""The Alembic history in migrations/: one head, reversible, and in sync with the models."""

import asyncio
from collections.abc import AsyncIterator, Callable

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.db import Database
from tests.conftest import TEST_DATABASE_URL

SERVICE_SCHEMAS = {"weather"}


@pytest.fixture
def alembic_config() -> Config:
    """Like alembic.ini, minus its logging setup (tests keep their own) and with the test URL."""
    config = Config()
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


def test_the_history_has_one_head(alembic_config: Config) -> None:
    # Two heads means two branches each added a migration: they must be merged into one line.
    assert len(ScriptDirectory.from_config(alembic_config).get_heads()) == 1


AlembicCommand = Callable[[Config, str], None]


async def run(alembic_command: AlembicCommand, config: Config, revision: str) -> None:
    # env.py starts its own event loop (as on the command line), so not on the test's loop.
    await asyncio.to_thread(alembic_command, config, revision)


async def schemas(database: Database) -> set[str]:
    async with database.engine.connect() as connection:
        rows = await connection.scalars(text("SELECT schema_name FROM information_schema.schemata"))
        return set(rows) & SERVICE_SCHEMAS


@pytest.fixture
async def migrated(database: Database, alembic_config: Config) -> AsyncIterator[None]:
    """Leaves the test database at head, as the other Postgres tests expect it."""
    yield
    await run(command.upgrade, alembic_config, "head")


@pytest.mark.postgres
async def test_upgrade_to_head_and_downgrade_to_base(
    database: Database, alembic_config: Config, migrated: None
) -> None:
    await run(command.downgrade, alembic_config, "base")
    assert await schemas(database) == set()

    await run(command.upgrade, alembic_config, "head")
    assert await schemas(database) == SERVICE_SCHEMAS

    await run(command.downgrade, alembic_config, "base")
    assert await schemas(database) == set()


@pytest.mark.postgres
async def test_the_models_match_the_migrations(
    database: Database, alembic_config: Config, migrated: None
) -> None:
    """A model change without a migration fails here (and in CI's `alembic check`)."""
    await run(command.upgrade, alembic_config, "head")

    await asyncio.to_thread(command.check, alembic_config)
