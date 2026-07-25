"""Create the module-boundary Postgres schemas.

Revision ID: 0001_create_schemas
Revises:
Create Date: 2026-07-25

"""
from alembic import op

revision = "0001_create_schemas"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ("content", "core", "game", "social", "mod", "srs")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')


def downgrade() -> None:
    for schema in reversed(SCHEMAS):
        op.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
