"""The weather service's tables, in schema `weather` (ARCHITECTURE.md §8.2).

A place is stored once in `locations`, keyed by its GeoNames id: the same id the API returns as
`location.id`. Everything that is the same in every language lives there; the names, which are
not ("Kyiv" / "Київ"), live in `location_names`, one row per place and language.
"""

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.language import Language

SCHEMA = "weather"

_LANGUAGES = ", ".join(f"'{language.value}'" for language in Language)


class LocationRow(Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        {"schema": SCHEMA},
    )

    # The GeoNames id, not a generated one: the provider assigns it, so the same place always
    # gets the same row, and ids in links (`/locations/{id}`, `?id=`) stay valid.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    latitude: Mapped[float] = mapped_column(Double)
    longitude: Mapped[float] = mapped_column(Double)
    timezone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # The last time the provider's data for this place was written.
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LocationNameRow(Base):
    __tablename__ = "location_names"
    __table_args__ = (
        CheckConstraint(f"language IN ({_LANGUAGES})", name="language"),
        {"schema": SCHEMA},
    )

    # Deleting a place deletes its names; nothing else points at a name.
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(LocationRow.id, ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
