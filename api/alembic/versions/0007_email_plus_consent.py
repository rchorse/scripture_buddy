"""Email-plus consent: token columns and the email_plus method.

Revision ID: 0007_email_plus
Revises: 0006_coppa_families
Create Date: 2026-08-03

Switches the default verifiable-consent method from a signed form to
"email plus" (consent link to the parent's email, followed by a delayed
confirmation email). The stricter methods remain available per-consent.
"""
import sqlalchemy as sa

from alembic import op

revision = "0007_email_plus"
down_revision = "0006_coppa_families"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("confirm_token_hash", sa.Text()),
    ("token_expires_at", sa.DateTime(timezone=True)),
    ("notice_sent_at", sa.DateTime(timezone=True)),
    ("followup_sent_at", sa.DateTime(timezone=True)),
]


def upgrade() -> None:
    for name, coltype in _COLUMNS:
        op.add_column(
            "parental_consents",
            sa.Column(name, coltype, nullable=True),
            schema="core",
        )
    op.drop_constraint(
        "ck_parental_consents_method_valid", "parental_consents", schema="core"
    )
    op.create_check_constraint(
        "method_valid",
        "parental_consents",
        "method IN ('email_plus','signed_form','card_charge','kba')",
        schema="core",
    )
    op.alter_column(
        "parental_consents",
        "method",
        server_default="email_plus",
        schema="core",
    )
    # Token lookups happen on every consent-link click.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_consents_token "
        "ON core.parental_consents (confirm_token_hash)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS core.ix_consents_token")
    op.drop_constraint(
        "ck_parental_consents_method_valid", "parental_consents", schema="core"
    )
    op.create_check_constraint(
        "method_valid",
        "parental_consents",
        "method IN ('signed_form','card_charge','kba')",
        schema="core",
    )
    for name, _ in _COLUMNS:
        op.drop_column("parental_consents", name, schema="core")
