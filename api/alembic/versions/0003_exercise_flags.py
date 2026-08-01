"""content.exercise_flags — learner reports on exercises.

Revision ID: 0003_exercise_flags
Revises: 0002_content_core_m1
Create Date: 2026-08-01

"""
import app.models.content  # noqa: F401
from alembic import op
from app.models import metadata

revision = "0003_exercise_flags"
down_revision = "0002_content_core_m1"
branch_labels = None
depends_on = None

_TABLE = "content.exercise_flags"


def upgrade() -> None:
    metadata.create_all(op.get_bind(), tables=[metadata.tables[_TABLE]], checkfirst=True)


def downgrade() -> None:
    metadata.drop_all(op.get_bind(), tables=[metadata.tables[_TABLE]], checkfirst=True)
