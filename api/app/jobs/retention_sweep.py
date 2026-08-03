"""Daily purge of accounts past their deletion grace period.

COPPA gives a parent the right to have their child's data deleted. This is the
job that actually does it — irreversibly, across every table, plus the Cognito
user and any consent evidence in S3.

The one thing deliberately kept is the `consent_audit` trail, with the consent
rows it references. That is the record proving consent was obtained and later
honoured; deleting it would destroy the evidence that the deletion was lawful.
It contains no content about the child beyond consent state changes.
"""
import logging
import os
from datetime import UTC, datetime

import boto3
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.content import ExerciseFlag
from app.models.core import (
    DeletionRequest,
    Device,
    Entitlement,
    FamilyMember,
    ParentalConsent,
    ReadingPosition,
    User,
)
from app.models.game import LeagueMember, Streak, UserBadge, UserStats, XpEvent
from app.models.srs import Card, ReviewLog

logger = logging.getLogger(__name__)


def _purge_user_data(session: Session, user_id) -> dict:
    """Delete every row belonging to this user, children first."""
    counts = {}

    card_ids = [
        c.id for c in session.scalars(select(Card).where(Card.user_id == user_id))
    ]
    if card_ids:
        counts["review_logs"] = session.execute(
            delete(ReviewLog).where(ReviewLog.card_id.in_(card_ids))
        ).rowcount
    for model, column in (
        (Card, Card.user_id),
        (XpEvent, XpEvent.user_id),
        (UserStats, UserStats.user_id),
        (Streak, Streak.user_id),
        (UserBadge, UserBadge.user_id),
        (LeagueMember, LeagueMember.user_id),
        (ReadingPosition, ReadingPosition.user_id),
        (Device, Device.user_id),
        (Entitlement, Entitlement.user_id),
        (ExerciseFlag, ExerciseFlag.user_id),
        (FamilyMember, FamilyMember.user_id),
    ):
        counts[model.__tablename__] = session.execute(
            delete(model).where(column == user_id)
        ).rowcount
    return counts


def _delete_consent_evidence(session: Session, user_id) -> int:
    """Remove uploaded signed forms from S3, keeping the audit rows."""
    bucket = os.environ.get("DATA_BUCKET")
    if not bucket:
        return 0
    client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    removed = 0
    for row in session.scalars(
        select(ParentalConsent).where(ParentalConsent.child_user_id == user_id)
    ):
        if not row.evidence_s3_key:
            continue
        try:
            client.delete_object(Bucket=bucket, Key=row.evidence_s3_key)
            removed += 1
        except Exception:  # noqa: BLE001 — a missing object must not block the purge
            logger.warning("could not delete consent evidence %s", row.evidence_s3_key)
        row.evidence_s3_key = ""
    return removed


def _delete_cognito_user(username: str) -> bool:
    pool_id = os.environ.get("USER_POOL_ID")
    if not pool_id or not username:
        return False
    client = boto3.client(
        "cognito-idp", region_name=os.environ.get("AWS_REGION", "us-west-2")
    )
    try:
        client.admin_delete_user(UserPoolId=pool_id, Username=username)
        return True
    except client.exceptions.UserNotFoundException:
        return False
    except Exception:  # noqa: BLE001 — never leave the DB half-purged
        logger.warning("could not delete Cognito user %s", username)
        return False


def retention_sweep(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    today = now.date()
    result = {"purged": 0, "users": []}

    with Session(get_engine()) as session:
        due = session.scalars(
            select(DeletionRequest).where(
                DeletionRequest.status == "pending",
                DeletionRequest.purge_after <= today,
            )
        ).all()

        for request in due:
            user = session.get(User, request.user_id)
            if user is None:
                request.status = "purged"
                request.purged_at = now
                continue

            username = user.username
            counts = _purge_user_data(session, user.id)
            evidence = _delete_consent_evidence(session, user.id)
            cognito_deleted = _delete_cognito_user(username)

            # Anonymize the row rather than deleting it, so the consent audit
            # trail keeps a valid foreign key. No personal data remains.
            user.username = f"deleted-{user.id.hex[:12]}"
            user.display_name = ""
            user.birth_date = None
            user.cognito_sub = None
            user.timezone = "UTC"
            user.status = "suspended"
            user.deleted_at = now

            request.status = "purged"
            request.purged_at = now
            result["purged"] += 1
            result["users"].append(
                {
                    "user_id": str(user.id),
                    "rows_deleted": {k: v for k, v in counts.items() if v},
                    "evidence_objects_deleted": evidence,
                    "cognito_deleted": cognito_deleted,
                }
            )
        session.commit()

    return {"status": "ok", **result}
