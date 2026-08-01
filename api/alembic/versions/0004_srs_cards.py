"""srs.cards and srs.review_logs — spaced repetition state.

Revision ID: 0004_srs_cards
Revises: 0003_exercise_flags
Create Date: 2026-08-01

"""
import app.models.srs  # noqa: F401
from alembic import op
from app.models import metadata

revision = "0004_srs_cards"
down_revision = "0003_exercise_flags"
branch_labels = None
depends_on = None

_TABLES = ["srs.cards", "srs.review_logs"]


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(
        bind, tables=[metadata.tables[t] for t in _TABLES], checkfirst=True
    )
    # The review queue is read on every session open; this index keeps it cheap.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cards_user_due ON srs.cards (user_id, due_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS srs.ix_cards_user_due")
    bind = op.get_bind()
    metadata.drop_all(
        bind, tables=[metadata.tables[t] for t in reversed(_TABLES)], checkfirst=True
    )
