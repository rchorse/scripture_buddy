"""Send the delayed confirmation email — the "plus" in email-plus.

A parent who did not actually consent gets an independent, unsolicited notice
that consent was recorded, with instructions to undo it. Runs on the hourly
schedule; each consent is followed up exactly once.
"""
import logging
import os

from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.core import User
from app.services import consent_email

logger = logging.getLogger(__name__)


def consent_followups() -> dict:
    base_url = os.environ.get("PUBLIC_API_URL", "")
    sent = 0
    skipped = 0

    with Session(get_engine()) as session:
        for consent in consent_email.due_for_followup(session):
            child = session.get(User, consent.child_user_id)
            parent = session.get(User, consent.parent_user_id)
            email = _parent_email(parent)
            if not email or child is None:
                # No address to write to; mark it so we don't retry forever.
                consent.followup_sent_at = consent.granted_at
                skipped += 1
                continue
            consent_email.send_followup(session, consent, child, email, base_url)
            sent += 1
        session.commit()

    return {"status": "ok", "followups_sent": sent, "skipped": skipped}


def _parent_email(parent: User | None) -> str:
    """Look up the parent's email from Cognito.

    Emails live in Cognito, not in our database — we hold as little personal
    information as possible.
    """
    if parent is None or not parent.cognito_sub:
        return ""
    import boto3

    pool_id = os.environ.get("USER_POOL_ID")
    if not pool_id:
        return ""
    client = boto3.client(
        "cognito-idp", region_name=os.environ.get("AWS_REGION", "us-west-2")
    )
    try:
        user = client.admin_get_user(UserPoolId=pool_id, Username=parent.username)
    except Exception:  # noqa: BLE001 — a missing Cognito user must not break the job
        logger.warning("could not read Cognito user for %s", parent.username)
        return ""
    for attr in user.get("UserAttributes", []):
        if attr["Name"] == "email":
            return attr["Value"]
    return ""
