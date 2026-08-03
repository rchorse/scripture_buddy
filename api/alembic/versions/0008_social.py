"""social schema: friends, blocks, parent approvals. Drops the social consent scope.

Revision ID: 0008_social
Revises: 0007_email_plus
Create Date: 2026-08-03

Under-13 accounts have no social surface (a fixed product decision), so the
`social` consent scope is removed — there is nothing for a parent to consent to.
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

    # No social scope any more. Nothing should have created one (the option
    # defaulted off), but clear any stragglers so the constraint can tighten.
    op.execute("DELETE FROM core.consent_audit WHERE consent_id IN "
               "(SELECT id FROM core.parental_consents WHERE scope = 'social')")
    op.execute("DELETE FROM core.parental_consents WHERE scope = 'social'")
    op.drop_constraint(
        "ck_parental_consents_scope_valid", "parental_consents", schema="core"
    )
    op.create_check_constraint(
        "scope_valid",
        "parental_consents",
        "scope IN ('account','ai_processing')",
        schema="core",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_parental_consents_scope_valid", "parental_consents", schema="core"
    )
    op.create_check_constraint(
        "scope_valid",
        "parental_consents",
        "scope IN ('account','ai_processing','social')",
        schema="core",
    )
    bind = op.get_bind()
    metadata.drop_all(
        bind, tables=[metadata.tables[t] for t in reversed(_TABLES)], checkfirst=True
    )
