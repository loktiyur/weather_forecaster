from sqlalchemy import Column, Integer, String, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.config import Settings
from app.core.db import Base, Database
from tests.conftest import UNREACHABLE_DATABASE_URL


async def test_ping_on_unreachable_postgres_returns_false() -> None:
    settings = Settings(
        _env_file=None, database_url=UNREACHABLE_DATABASE_URL, database_timeout_seconds=0.2
    )
    database = Database(settings)

    assert await database.ping() is False
    await database.dispose()


def test_engine_uses_settings() -> None:
    url = "postgresql+asyncpg://user:secret@pg:5440/app"
    database = Database(Settings(_env_file=None, database_url=url))

    assert database.engine.url.render_as_string(hide_password=False) == url
    assert database.engine.dialect.driver == "asyncpg"


def test_constraints_get_predictable_names() -> None:
    # Alembic (Phase 8.3) relies on these names being the same on every machine.
    table = Table(
        "probe",
        Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("code", String, unique=True),
    )
    try:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]
    finally:
        Base.metadata.remove(table)  # keep the shared metadata free of test tables

    assert "CONSTRAINT pk_probe PRIMARY KEY (id)" in ddl
    assert "CONSTRAINT uq_probe_code UNIQUE (code)" in ddl
