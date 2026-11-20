"""Create weather.locations and weather.location_names

Places keyed by their GeoNames id, and their names per language.

Revision ID: 98d8a094c555
Revises: b63ff8d1a5fb
Create Date: 2026-11-20 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "98d8a094c555"
down_revision: str | Sequence[str] | None = "b63ff8d1a5fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("latitude", sa.Double(), nullable=False),
        sa.Column("longitude", sa.Double(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name=op.f("ck_locations_latitude_range")),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_locations_longitude_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        schema="weather",
    )
    op.create_table(
        "location_names",
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "language IN ('en', 'uk', 'cs', 'ru')", name=op.f("ck_location_names_language")
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["weather.locations.id"],
            name=op.f("fk_location_names_location_id_locations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("location_id", "language", name=op.f("pk_location_names")),
        schema="weather",
    )


def downgrade() -> None:
    op.drop_table("location_names", schema="weather")
    op.drop_table("locations", schema="weather")
