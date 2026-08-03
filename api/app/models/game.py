"""game schema — XP, streaks, badges, collectibles, leagues.

`xp_events` is the append-only source of truth; `user_stats` is a denormalized
projection updated in the same transaction. Anything else (levels, league
standings, badge eligibility) derives from the ledger, so a bug in a projection
can always be repaired by replaying it.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

SCHEMA = "game"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class XpEvent(Base):
    """Append-only. Never updated or deleted."""

    __tablename__ = "xp_events"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)  # lesson | review | streak_bonus | quest
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class UserStats(Base):
    """Denormalized projection of xp_events — rebuildable from the ledger."""

    __tablename__ = "user_stats"
    __table_args__ = ({"schema": SCHEMA},)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.users.id"), primary_key=True
    )
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    lessons_done: Mapped[int] = mapped_column(Integer, default=0)
    answers_correct: Mapped[int] = mapped_column(Integer, default=0)
    answers_total: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class Streak(Base):
    """Streak state in the user's OWN timezone.

    `last_active_local_date` is a local calendar date, never a UTC date — a
    learner in Auckland must not lose a streak because UTC rolled over.
    """

    __tablename__ = "streaks"
    __table_args__ = ({"schema": SCHEMA},)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.users.id"), primary_key=True
    )
    current: Mapped[int] = mapped_column(Integer, default=0)
    longest: Mapped[int] = mapped_column(Integer, default=0)
    last_active_local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    freezes_available: Mapped[int] = mapped_column(Integer, default=1)
    freeze_used_dates: Mapped[list[date]] = mapped_column(ARRAY(Date), default=list)
    # Local date this user was last rolled over, so the hourly job is idempotent.
    last_rollover_local_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Badge(Base):
    """Badges are data: adding one is a row plus an art asset, not a deploy."""

    __tablename__ = "badges"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    art_key: Mapped[str] = mapped_column(Text, default="")
    # e.g. {"type": "streak", "gte": 7} — see services/badges.py
    rule: Mapped[dict] = mapped_column(JSONB)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_user_badges"),
        {"schema": SCHEMA},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.users.id"), primary_key=True
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.badges.id"), primary_key=True
    )
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class LeagueTier(Base):
    __tablename__ = "league_tiers"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = _uuid_pk()
    rank: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(Text)


class LeagueCohort(Base):
    __tablename__ = "league_cohorts"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = _uuid_pk()
    tier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.league_tiers.id"))
    week_start: Mapped[date] = mapped_column(Date)


class LeagueMember(Base):
    __tablename__ = "league_members"
    __table_args__ = (
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('promote','stay','demote')",
            name="outcome_valid",
        ),
        {"schema": SCHEMA},
    )

    cohort_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.league_cohorts.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.users.id"), primary_key=True
    )
    final_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
