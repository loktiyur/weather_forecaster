"""SQL for the weather service's tables. The only module of the service that writes SQL."""

from collections.abc import Iterable
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.language import Language
from app.services.weather.models import LocationNameRow, LocationRow
from app.services.weather.schemas import Location


class LocationStoreError(Exception):
    """The stored places cannot be read or written (Postgres down, timeout, ...)."""


class LocationStore(Protocol):
    """Places already seen, by id. `LocationRepository` is the Postgres implementation."""

    async def get(self, location_id: int, language: Language) -> Location | None:
        """The place with its names in `language`; None if it was never stored in it."""
        ...

    async def save(self, locations: Iterable[Location], language: Language) -> None:
        """Insert or update the places and their names in `language`. Places without an id
        are skipped."""
        ...


class LocationRepository:
    """`LocationStore` on Postgres. Opens one short session per call, so it can live as long
    as the app (like the service that uses it) without holding a connection."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, location_id: int, language: Language) -> Location | None:
        query = (
            select(LocationRow, LocationNameRow)
            .join(LocationNameRow, LocationNameRow.location_id == LocationRow.id)
            .where(LocationRow.id == location_id, LocationNameRow.language == language.value)
        )
        try:
            async with self._sessions() as session:
                row = (await session.execute(query)).one_or_none()
        except (SQLAlchemyError, OSError) as exc:
            raise LocationStoreError(str(exc)) from exc
        if row is None:
            return None
        place, names = row
        return Location(
            id=place.id,
            name=names.name,
            country=names.country,
            country_code=place.country_code,
            region=names.region,
            latitude=place.latitude,
            longitude=place.longitude,
            timezone=place.timezone,
        )

    async def save(self, locations: Iterable[Location], language: Language) -> None:
        # One row per id: Postgres refuses to update the same row twice in one INSERT. Sorted,
        # so two requests saving overlapping places lock the rows in the same order and cannot
        # deadlock.
        by_id = {place.id: place for place in locations if place.id is not None}
        places = [by_id[place_id] for place_id in sorted(by_id)]
        if not places:
            return

        insert_places = insert(LocationRow).values(
            [
                {
                    "id": place.id,
                    "country_code": place.country_code,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "timezone": place.timezone,
                }
                for place in places
            ]
        )
        upsert_places = insert_places.on_conflict_do_update(
            index_elements=[LocationRow.id],
            set_={
                "country_code": insert_places.excluded.country_code,
                "latitude": insert_places.excluded.latitude,
                "longitude": insert_places.excluded.longitude,
                "timezone": insert_places.excluded.timezone,
                "updated_at": func.now(),
            },
        )
        insert_names = insert(LocationNameRow).values(
            [
                {
                    "location_id": place.id,
                    "language": language.value,
                    "name": place.name,
                    "country": place.country,
                    "region": place.region,
                }
                for place in places
            ]
        )
        upsert_names = insert_names.on_conflict_do_update(
            index_elements=[LocationNameRow.location_id, LocationNameRow.language],
            set_={
                "name": insert_names.excluded.name,
                "country": insert_names.excluded.country,
                "region": insert_names.excluded.region,
            },
        )
        try:
            # One transaction: a place is never stored without its names.
            async with self._sessions.begin() as session:
                await session.execute(upsert_places)
                await session.execute(upsert_names)
        except (SQLAlchemyError, OSError) as exc:
            raise LocationStoreError(str(exc)) from exc
