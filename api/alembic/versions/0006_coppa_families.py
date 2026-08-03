"""COPPA: families, per-scope consent, audit trail, deletion, policy, devices.

Revision ID: 0006_coppa_families
Revises: 0005_game_tables
Create Date: 2026-08-03

Also extends core.users with the columns the age gate and consent flow need.
"""
import sqlalchemy as sa

import app.models.core  # noqa: F401
from alembic import op
from app.models import metadata

revision = "0006_coppa_families"
down_revision = "0005_game_tables"
branch_labels = None
depends_on = None

_NEW_TABLES = [
    "core.families",
    "core.family_members",
    "core.parental_consents",
    "core.consent_audit",
    "core.deletion_requests",
    "core.policy_flags",
    "core.devices",
    "core.entitlements",
]

_USER_COLUMNS = [
    ("display_name_status", sa.Text(), "'ok'"),
    ("birth_date", sa.Date(), None),
    ("status", sa.Text(), "'active'"),
    ("is_owner", sa.Boolean(), "false"),
    ("deleted_at", sa.DateTime(timezone=True), None),
]


def upgrade() -> None:
    bind = op.get_bind()

    for name, coltype, default in _USER_COLUMNS:
        op.add_column(
            "users",
            sa.Column(
                name,
                coltype,
                nullable=True,
                server_default=sa.text(default) if default else None,
            ),
            schema="core",
        )

    # cognito_sub becomes nullable: a parent-created child has no Cognito
    # identity until they first sign in and claim the account.
    op.alter_column("users", "cognito_sub", nullable=True, schema="core")

    op.create_check_constraint(
        "status_valid",
        "users",
        "status IN ('pending_consent','active','suspended','deletion_pending')",
        schema="core",
    )
    op.create_check_constraint(
        "display_name_status_valid",
        "users",
        "display_name_status IN ('ok','pending','flagged')",
        schema="core",
    )

    metadata.create_all(
        bind, tables=[metadata.tables[t] for t in _NEW_TABLES], checkfirst=True
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_consents_child "
        "ON core.parental_consents (child_user_id, scope)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_deletion_pending "
        "ON core.deletion_requests (status, purge_after)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(
        bind, tables=[metadata.tables[t] for t in reversed(_NEW_TABLES)], checkfirst=True
    )
    op.drop_constraint("ck_users_display_name_status_valid", "users", schema="core")
    op.drop_constraint("ck_users_status_valid", "users", schema="core")
    for name, _, _ in _USER_COLUMNS:
        op.drop_column("users", name, schema="core")
