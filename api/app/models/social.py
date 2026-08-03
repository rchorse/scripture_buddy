"""social schema — friends and blocks.

There is no messaging in ScriptureBuddy and never will be. "Social" here means
exactly two things: seeing an approved friend's progress, and appearing
alongside them on a leaderboard.

Two safety rules are structural:

1. A friendship needs BOTH parties to agree. A request is not a connection.
2. A minor's friendship additionally needs their parent's approval, which is a
   distinct step from the other learner accepting.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

SCHEMA = "social"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class FriendRequest(Base):
    """A pending connection.

    `status` walks: pending → awaiting_parent → accepted, with declined /
    cancelled / expired as terminal states. `awaiting_parent` is entered when
    either side is a minor, and needs approval from THAT side's parent.
    """

    __tablename__ = "friend_requests"
    __table_args__ = (
        UniqueConstraint("from_user_id", "to_user_id", name="uq_friend_request_pair"),
        CheckConstraint("from_user_id <> to_user_id", name="no_self_request"),
        CheckConstraint(
            "status IN ('pending','awaiting_parent','accepted','declined',"
            "'cancelled','expired')",
            name="status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    from_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    status: Mapped[str] = mapped_column(Text, default="pending")
    # Who still owes an approval is derived from ParentApproval rows, not
    # duplicated here — one source of truth.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Friendship(Base):
    """An accepted, fully approved connection.

    Stored once with `user_a < user_b` so a pair can never be duplicated in
    mirror image.
    """

    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("user_a < user_b", name="ordered_pair"),
        {"schema": SCHEMA},
    )

    user_a: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.users.id"), primary_key=True
    )
    user_b: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.users.id"), primary_key=True
    )
    since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Block(Base):
    """One-way block. Hides content both ways and blocks future requests."""

    __tablename__ = "blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_block_pair"),
        CheckConstraint("blocker_id <> blocked_id", name="no_self_block"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    blocker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    blocked_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ParentApproval(Base):
    """A parent signing off on one specific friendship for their child."""

    __tablename__ = "parent_approvals"
    __table_args__ = (
        UniqueConstraint(
            "request_id", "child_user_id", name="uq_parent_approval_request_child"
        ),
        CheckConstraint(
            "decision IN ('pending','approved','denied')", name="decision_valid"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.friend_requests.id")
    )
    child_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    parent_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"))
    decision: Mapped[str] = mapped_column(Text, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
