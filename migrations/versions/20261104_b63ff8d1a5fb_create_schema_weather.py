"""Create schema weather

The weather service's tables go there; the first one comes in Phase 8.4.

Revision ID: b63ff8d1a5fb
Revises:
Create Date: 2026-11-04 12:56:52.122943
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b63ff8d1a5fb"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA weather")


def downgrade() -> None:
    # RESTRICT: refuses to drop the schema while it still has tables (none at this revision).
    op.execute("DROP SCHEMA weather RESTRICT")
