"""srs schema — spaced repetition scheduling state.

One card per (user, exercise). FSRS-style parameters: `stability` is the number
of days until recall probability decays to ~90%, `difficulty` is an intrinsic
1–10 hardness that drifts with performance. review_logs is append-only so the
scheduler's parameters can be re-fit against real data later.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

SCHEMA = "srs"


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("user_id", "exercise_id", name="uq_cards_user_exercise"),
        CheckConstraint(
            "state IN ('new','learning','review','lapsed')", name="state_valid"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    exercise_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content.exercises.id"))
    state: Mapped[str] = mapped_column(Text, default="new")
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=5.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewLog(Base):
    """Append-only. Never updated or deleted."""

    __tablename__ = "review_logs"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 4", name="rating_valid"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.cards.id"))
    rating: Mapped[int] = mapped_column(Integer)
    elapsed_days: Mapped[float] = mapped_column(Float, default=0.0)
    scheduled_days: Mapped[float] = mapped_column(Float, default=0.0)
    stability_after: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty_after: Mapped[float] = mapped_column(Float, default=5.0)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
