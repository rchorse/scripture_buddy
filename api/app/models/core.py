"""core schema — identity, families, consent, policy.

COPPA shapes this module. Two rules are enforced structurally, not by
convention:

1. A child's row carries no email, phone, real name, or geolocation. There are
   no columns for them, so no code path can accidentally persist them.
2. `birth_date` is the only age input, and the bracket is always derived from
   it server-side (see services/ages.py) — never accepted from a client.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
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

SCHEMA = "core"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_consent','active','suspended','deletion_pending')",
            name="status_valid",
        ),
        CheckConstraint(
            "display_name_status IN ('ok','pending','flagged')",
            name="display_name_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Null until a parent-created child first signs in and claims the account.
    cognito_sub: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text, default="")
    display_name_status: Mapped[str] = mapped_column(Text, default="ok")
    # The single source of age truth. Nullable only for legacy adult accounts
    # created before the age gate existed.
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(Text, default="UTC")  # IANA name
    status: Mapped[str] = mapped_column(Text, default="active")
    is_owner: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Family(Base):
    __tablename__ = "families"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class FamilyMember(Base):
    __tablename__ = "family_members"
    __table_args__ = (
        CheckConstraint("relation IN ('parent','child')", name="relation_valid"),
        {"schema": SCHEMA},
    )

    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.families.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ParentalConsent(Base):
    """One row per scope.

    The 2026 COPPA amendments require separate consent for distinct uses, so
    consenting to an account is not consent to AI processing or to social
    features. Each scope is granted, and revocable, independently.
    """

    __tablename__ = "parental_consents"
    __table_args__ = (
        UniqueConstraint("child_user_id", "scope", name="uq_consent_child_scope"),
        CheckConstraint(
            "scope IN ('account','ai_processing','social')", name="scope_valid"
        ),
        CheckConstraint(
            "status IN ('pending','granted','revoked','denied')", name="status_valid"
        ),
        CheckConstraint(
            "method IN ('email_plus','signed_form','card_charge','kba')",
            name="method_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    child_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    parent_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    scope: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text, default="email_plus")
    status: Mapped[str] = mapped_column(Text, default="pending")
    # S3 key of a signed form, when the stricter method is used.
    evidence_s3_key: Mapped[str] = mapped_column(Text, default="")
    # email_plus: one-time link, stored only as a hash so a leak can't be replayed.
    confirm_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notice_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The "plus" step: delayed confirmation giving the parent a chance to undo.
    followup_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class ConsentAudit(Base):
    """Append-only. Every consent state change, forever."""

    __tablename__ = "consent_audit"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = _uuid_pk()
    consent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.parental_consents.id")
    )
    event: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class DeletionRequest(Base):
    """A parent (or adult) asking for an account to be erased.

    The account is disabled immediately; the purge runs after a grace period so
    an accidental request can be undone.
    """

    __tablename__ = "deletion_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','cancelled','purged')", name="status_valid"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="pending")
    purge_after: Mapped[date] = mapped_column(Date)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PolicyFlag(Base):
    """Server-side feature policy, changeable without a deploy."""

    __tablename__ = "policy_flags"
    __table_args__ = ({"schema": SCHEMA},)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class Device(Base):
    """Push tokens. Kept only while the account is active and consented."""

    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("fcm_token", name="uq_devices_token"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    fcm_token: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text, default="")
    reminder_hour_local: Mapped[int] = mapped_column(Integer, default=19)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Entitlement(Base):
    """Payments-agnostic feature grants.

    A future Stripe or StoreKit integration only ever writes rows here; every
    feature check reads from this table, so monetization can change without
    touching feature code.
    """

    __tablename__ = "entitlements"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    key: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="grant")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReadingPosition(Base):
    __tablename__ = "reading_positions"
    __table_args__ = ({"schema": SCHEMA},)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id"), primary_key=True
    )
    work_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content.works.id"), primary_key=True
    )
    division_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content.divisions.id"))
    verse_position: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )
