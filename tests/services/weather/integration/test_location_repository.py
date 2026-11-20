"""`LocationRepository` and the two tables behind it, on the real test Postgres."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.db import Database
from app.core.language import Language
from app.services.weather.repository import LocationRepository, LocationStoreError
from app.services.weather.schemas import Location

pytestmark = pytest.mark.postgres

KYIV = Location(
    id=703448,
    name="Kyiv",
    country="Ukraine",
    country_code="UA",
    region="Kyiv City",
    latitude=50.45466,
    longitude=30.5238,
    timezone="Europe/Kyiv",
)
KYIV_UK = KYIV.model_copy(update={"name": "Київ", "country": "Україна", "region": "Місто Київ"})
LVIV = Location(id=702550, name="Lviv", country_code="UA", latitude=49.84, longitude=24.02)


@pytest.fixture
def repository(clean_database: Database) -> LocationRepository:
    return LocationRepository(clean_database.sessions)


async def count(database: Database, table: str) -> int:
    async with database.engine.connect() as connection:
        return int(await connection.scalar(text(f"SELECT count(*) FROM {table}")) or 0)


async def test_a_saved_place_is_read_back(repository: LocationRepository) -> None:
    await repository.save([KYIV], Language.EN)

    assert await repository.get(703448, Language.EN) == KYIV


async def test_an_unknown_id_is_none(repository: LocationRepository) -> None:
    assert await repository.get(703448, Language.EN) is None


async def test_names_are_kept_per_language(
    repository: LocationRepository, clean_database: Database
) -> None:
    await repository.save([KYIV], Language.EN)

    assert await repository.get(703448, Language.UK) is None  # not stored in Ukrainian yet

    await repository.save([KYIV_UK], Language.UK)

    assert await repository.get(703448, Language.EN) == KYIV
    assert await repository.get(703448, Language.UK) == KYIV_UK
    assert await count(clean_database, "weather.locations") == 1
    assert await count(clean_database, "weather.location_names") == 2


async def test_saving_again_updates_the_place(
    repository: LocationRepository, clean_database: Database
) -> None:
    await repository.save([KYIV], Language.EN)
    moved = KYIV.model_copy(update={"name": "Kyiv (new)", "latitude": 50.5, "timezone": None})

    await repository.save([moved], Language.EN)

    assert await repository.get(703448, Language.EN) == moved
    assert await count(clean_database, "weather.locations") == 1
    async with clean_database.engine.connect() as connection:
        created, updated = (
            await connection.execute(
                text("SELECT created_at, updated_at FROM weather.locations WHERE id = 703448")
            )
        ).one()
    assert updated > created  # each save is its own transaction, so now() moved on


async def test_many_places_in_one_save(
    repository: LocationRepository, clean_database: Database
) -> None:
    no_id = Location(name="Somewhere", latitude=1, longitude=2)

    # The same place twice in one INSERT would be "ON CONFLICT DO UPDATE command cannot
    # affect row a second time"; the repository keeps one of them.
    await repository.save([KYIV, LVIV, KYIV, no_id], Language.EN)

    assert await repository.get(702550, Language.EN) == LVIV
    assert await count(clean_database, "weather.locations") == 2


async def test_saving_nothing_is_a_no_op(repository: LocationRepository) -> None:
    await repository.save([], Language.EN)
    await repository.save([Location(name="No id", latitude=1, longitude=2)], Language.EN)


async def test_deleting_a_place_deletes_its_names(
    repository: LocationRepository, clean_database: Database
) -> None:
    await repository.save([KYIV], Language.EN)
    await repository.save([KYIV_UK], Language.UK)

    async with clean_database.engine.begin() as connection:
        await connection.execute(text("DELETE FROM weather.locations WHERE id = 703448"))

    assert await count(clean_database, "weather.location_names") == 0


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO weather.locations (id, latitude, longitude) VALUES (1, 91, 0)",
        "INSERT INTO weather.locations (id, latitude, longitude) VALUES (1, 0, -181)",
        "INSERT INTO weather.location_names (location_id, language, name) VALUES (42, 'en', 'x')",
        "INSERT INTO weather.locations (id, latitude, longitude) VALUES (1, 0, 0);"
        "INSERT INTO weather.location_names (location_id, language, name) VALUES (1, 'de', 'x')",
    ],
    ids=["latitude", "longitude", "name-without-place", "unknown-language"],
)
async def test_the_database_rejects_invalid_rows(clean_database: Database, statement: str) -> None:
    with pytest.raises(IntegrityError):
        async with clean_database.engine.begin() as connection:
            for single in statement.split(";"):
                await connection.execute(text(single))


async def test_an_unreachable_database_raises_location_store_error(settings: Settings) -> None:
    database = Database(settings)  # the test settings point at a closed port
    repository = LocationRepository(database.sessions)

    with pytest.raises(LocationStoreError):
        await repository.get(703448, Language.EN)
    with pytest.raises(LocationStoreError):
        await repository.save([KYIV], Language.EN)
    await database.dispose()
