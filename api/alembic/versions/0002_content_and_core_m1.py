"""content library tables + minimal core (users, reading_positions).

Revision ID: 0002_content_core_m1
Revises: 0001_create_schemas
Create Date: 2026-07-31

Tables are created from the model metadata: at this pre-release stage the
models ARE the schema source of truth, and creating from metadata avoids
hand-transcription drift. Post-release migrations must be explicit ops.
"""
import app.models.content
import app.models.core  # noqa: F401
from alembic import op
from app.models import metadata

revision = "0002_content_core_m1"
down_revision = "0001_create_schemas"
branch_labels = None
depends_on = None

_TABLES = [
    "content.works",
    "content.editions",
    "content.divisions",
    "content.verses",
    "content.lessons",
    "content.exercises",
    "content.releases",
    "content.release_items",
    "content.book_requests",
    "core.users",
    "core.reading_positions",
]


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(
        bind, tables=[metadata.tables[name] for name in _TABLES], checkfirst=True
    )


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(
        bind, tables=[metadata.tables[name] for name in reversed(_TABLES)], checkfirst=True
    )
