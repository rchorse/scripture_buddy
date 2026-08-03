"""game schema — XP ledger, stats, streaks, badges, leagues. Seeds starter badges.

Revision ID: 0005_game_tables
Revises: 0004_srs_cards
Create Date: 2026-08-01

"""
import json

import app.models.game  # noqa: F401
from alembic import op
from app.models import metadata
from app.services.badges import STARTER_BADGES

revision = "0005_game_tables"
down_revision = "0004_srs_cards"
branch_labels = None
depends_on = None

_TABLES = [
    "game.xp_events",
    "game.user_stats",
    "game.streaks",
    "game.badges",
    "game.user_badges",
    "game.league_tiers",
    "game.league_cohorts",
    "game.league_members",
]

_TIERS = ["Bronze", "Silver", "Gold", "Sapphire", "Ruby", "Diamond"]


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(
        bind, tables=[metadata.tables[t] for t in _TABLES], checkfirst=True
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_xp_events_user_awarded "
        "ON game.xp_events (user_id, awarded_at)"
    )

    # Seed badges and league tiers. Idempotent so a re-run is safe.
    for badge in STARTER_BADGES:
        op.execute(
            "INSERT INTO game.badges (slug, title, description, art_key, rule, sort_order) "
            f"VALUES ('{badge['slug']}', '{badge['title']}', "
            f"'{badge['description'].replace(chr(39), chr(39) * 2)}', '{badge['art_key']}', "
            f"'{json.dumps(badge['rule'])}'::jsonb, {badge['sort_order']}) "
            "ON CONFLICT (slug) DO NOTHING"
        )
    for rank, name in enumerate(_TIERS, start=1):
        op.execute(
            f"INSERT INTO game.league_tiers (rank, name) VALUES ({rank}, '{name}') "
            "ON CONFLICT (rank) DO NOTHING"
        )


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(
        bind, tables=[metadata.tables[t] for t in reversed(_TABLES)], checkfirst=True
    )
