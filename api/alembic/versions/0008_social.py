"""social schema: friends, blocks, parent approvals.

Revision ID: 0008_social
Revises: 0007_email_plus
Create Date: 2026-08-03

Under-13 accounts may use friends and leaderboards when their parent has
granted the `social` consent scope. There is no chat anywhere in the app.
"""
import app.models.social  # noqa: F401
from alembic import op
from app.models import metadata

revision = "0008_social"
down_revision = "0007_email_plus"
branch_labels = None
depends_on = None

_TABLES = [
    "social.friend_requests",
    "social.friendships",
    "social.blocks",
    "social.parent_approvals",
]


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(
        bind, tables=[metadata.tables[t] for t in _TABLES], checkfirst=True
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_friend_requests_to "
        "ON social.friend_requests (to_user_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_parent_approvals_parent "
        "ON social.parent_approvals (parent_user_id, decision)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(
        bind, tables=[metadata.tables[t] for t in reversed(_TABLES)], checkfirst=True
    )
