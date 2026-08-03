import os
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

import boto3
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.principal import (
    bracket_of,
    get_current_user,
    require_adult,
    require_parent_of,
)
from app.jobs.consent_followups import _parent_email
from app.models.core import (
    DeletionRequest,
    Family,
    FamilyMember,
    ParentalConsent,
    User,
)
from app.services import ages, consent, consent_email

router = APIRouter(prefix="/family", tags=["family"])

# Days between a deletion request and the irreversible purge.
DELETION_GRACE_DAYS = 30


@router.post("/age-gate")
def age_gate(body: dict, db: Session = Depends(get_db)):
    """Neutral age gate, called BEFORE any account is created.

    Deliberately unauthenticated and side-effect free: it collects nothing and
    stores nothing. Under-13s are told a parent must set the account up — we
    never let them proceed to a signup form, because doing so would collect
    personal information from a child without verifiable parental consent.
    """
    raw = body.get("birth_date")
    if not raw:
        raise HTTPException(status_code=400, detail="birth_date is required")
    try:
        birth_date = date.fromisoformat(raw)
        bracket = ages.bracket_for(birth_date, datetime.now(UTC).date())
    except (ValueError, ages.InvalidBirthDate) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid birth date: {exc}")

    return {
        "bracket": bracket,
        "can_self_register": ages.can_self_register(bracket),
        "requires_parent": bracket == ages.UNDER_13,
        "message": (
            "A parent or guardian needs to create this account for you."
            if bracket == ages.UNDER_13
            else "You can create your account."
        ),
    }


@router.get("")
def my_family(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The household this user belongs to, from either side."""
    memberships = db.scalars(
        select(FamilyMember).where(FamilyMember.user_id == user.id)
    ).all()
    if not memberships:
        return {"family": None, "role": None, "children": [], "parents": []}

    membership = memberships[0]
    family = db.get(Family, membership.family_id)
    others = db.scalars(
        select(FamilyMember).where(FamilyMember.family_id == family.id)
    ).all()

    def describe(member: FamilyMember) -> dict:
        member_user = db.get(User, member.user_id)
        scopes = consent.granted_scopes(db, member_user.id)
        return {
            "user_id": str(member_user.id),
            "username": member_user.username,
            "display_name": member_user.display_name,
            "relation": member.relation,
            "status": member_user.status,
            "bracket": bracket_of(member_user),
            "consents": sorted(scopes),
            "claimed": member_user.cognito_sub is not None,
        }

    return {
        "family": {"id": str(family.id), "name": family.name},
        "role": membership.relation,
        "children": [describe(m) for m in others if m.relation == "child"],
        "parents": [describe(m) for m in others if m.relation == "parent"],
    }


@router.post("/children")
def create_child(
    body: dict,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    """A verified adult creates a child account.

    Only a username, birth date and timezone are collected — deliberately no
    email, phone, real name or location. The account is unusable until the
    owner verifies the signed consent form.
    """
    username = (body.get("username") or "").strip().lower()
    raw_birth = body.get("birth_date")
    if not username or not raw_birth:
        raise HTTPException(status_code=400, detail="username and birth_date required")
    if not 3 <= len(username) <= 30 or not username.replace("-", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-30 characters, letters, numbers and hyphens.",
        )
    try:
        birth_date = ages.validate_birth_date(
            date.fromisoformat(raw_birth), datetime.now(UTC).date()
        )
    except (ValueError, ages.InvalidBirthDate) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid birth date: {exc}")

    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="That username is taken.")

    bracket = ages.bracket_for(birth_date, datetime.now(UTC).date())
    child = User(
        username=username,
        display_name=body.get("display_name", "")[:40],
        birth_date=birth_date,
        timezone=body.get("timezone", parent.timezone),
        # Under-13 needs verified consent first; teens are usable immediately.
        status="pending_consent" if bracket == ages.UNDER_13 else "active",
    )
    db.add(child)
    db.flush()

    family = _family_for_parent(db, parent)
    db.add(FamilyMember(family_id=family.id, user_id=child.id, relation="child"))

    scopes = ["account"]
    if body.get("allow_ai_processing", True):
        scopes.append("ai_processing")
    consents = (
        consent.request_consent(db, child, parent, scopes)
        if bracket == ages.UNDER_13
        else []
    )

    # Email-plus: send the consent notice to the parent's own email, which we
    # already hold in Cognito because they are a verified adult account holder.
    notices = []
    parent_email = _parent_email(parent)
    base_url = os.environ.get("PUBLIC_API_URL", "")
    for row in consents:
        result = consent_email.issue_notice(db, row, child, parent_email, base_url)
        notices.append({"scope": row.scope, "delivered": result["delivered"]})
    db.commit()

    return {
        "user_id": str(child.id),
        "username": child.username,
        "bracket": bracket,
        "status": child.status,
        "requires_consent": bracket == ages.UNDER_13,
        "pending_consents": [
            {"id": str(c.id), "scope": c.scope, "status": c.status} for c in consents
        ],
        "consent_notices": notices,
        "parent_email_on_file": bool(parent_email),
    }


def _family_for_parent(db: Session, parent: User) -> Family:
    membership = db.scalar(
        select(FamilyMember).where(
            FamilyMember.user_id == parent.id, FamilyMember.relation == "parent"
        )
    )
    if membership is not None:
        return db.get(Family, membership.family_id)
    family = Family(name=f"{parent.display_name or parent.username}'s family", created_by=parent.id)
    db.add(family)
    db.flush()
    db.add(FamilyMember(family_id=family.id, user_id=parent.id, relation="parent"))
    return family


@router.post("/children/{child_id}/set-password")
def set_child_password(
    child_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    """Create or reset the child's Cognito sign-in.

    The parent sets it; the child signs in with username + password only. No
    email is ever attached to a child account.
    """
    child = require_parent_of(db, parent, child_id)
    password = body.get("password") or ""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be 8+ characters.")

    client = boto3.client(
        "cognito-idp", region_name=os.environ.get("AWS_REGION", "us-west-2")
    )
    pool_id = os.environ["USER_POOL_ID"]
    try:
        client.admin_create_user(
            UserPoolId=pool_id,
            Username=child.username,
            MessageAction="SUPPRESS",
        )
    except client.exceptions.UsernameExistsException:
        pass
    client.admin_set_user_password(
        UserPoolId=pool_id,
        Username=child.username,
        Password=password,
        Permanent=True,
    )
    db.commit()
    return {"status": "ok", "username": child.username}


@router.get("/children/{child_id}/consents")
def child_consents(
    child_id: uuid.UUID,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    child = require_parent_of(db, parent, child_id)
    rows = db.scalars(
        select(ParentalConsent).where(ParentalConsent.child_user_id == child.id)
    ).all()
    return [
        {
            "id": str(c.id),
            "scope": c.scope,
            "status": c.status,
            "method": c.method,
            "has_evidence": bool(c.evidence_s3_key),
            "granted_at": c.granted_at.isoformat() if c.granted_at else None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        }
        for c in rows
    ]


@router.post("/consents/{consent_id}/evidence-url")
def consent_evidence_url(
    consent_id: uuid.UUID,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    """Presigned PUT so the signed form goes straight to S3.

    The form never passes through the API, and the bucket stays private — the
    owner reads it via a short-lived presigned GET in the admin queue.
    """
    row = db.get(ParentalConsent, consent_id)
    if row is None:
        raise HTTPException(status_code=404)
    require_parent_of(db, parent, row.child_user_id)

    key = f"consents/{row.child_user_id}/{consent_id}/{secrets.token_hex(8)}.pdf"
    client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": os.environ["DATA_BUCKET"],
            "Key": key,
            "ContentType": "application/pdf",
        },
        ExpiresIn=900,
    )
    consent.attach_evidence(db, row, key, actor_id=parent.id)
    db.commit()
    return {"upload_url": url, "key": key, "expires_in": 900}


@router.post("/consents/{consent_id}/revoke")
def revoke(
    consent_id: uuid.UUID,
    body: dict | None = None,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    row = db.get(ParentalConsent, consent_id)
    if row is None:
        raise HTTPException(status_code=404)
    require_parent_of(db, parent, row.child_user_id)
    consent.revoke_consent(db, row, parent, reason=(body or {}).get("reason", ""))
    db.commit()
    return {"status": "revoked", "scope": row.scope}


@router.post("/children/{child_id}/delete")
def request_child_deletion(
    child_id: uuid.UUID,
    body: dict | None = None,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    """A parent exercising the COPPA right to have a child's data deleted.

    The account is disabled immediately; the irreversible purge runs after a
    grace period so an accidental request can be undone.
    """
    child = require_parent_of(db, parent, child_id)
    existing = db.scalar(
        select(DeletionRequest).where(
            DeletionRequest.user_id == child.id, DeletionRequest.status == "pending"
        )
    )
    if existing is not None:
        return {
            "status": "already_pending",
            "purge_after": existing.purge_after.isoformat(),
        }

    request = DeletionRequest(
        user_id=child.id,
        requested_by=parent.id,
        reason=(body or {}).get("reason", ""),
        purge_after=datetime.now(UTC).date() + timedelta(days=DELETION_GRACE_DAYS),
    )
    db.add(request)
    child.status = "deletion_pending"
    db.commit()
    return {
        "status": "pending",
        "purge_after": request.purge_after.isoformat(),
        "grace_days": DELETION_GRACE_DAYS,
    }


@router.post("/children/{child_id}/cancel-deletion")
def cancel_child_deletion(
    child_id: uuid.UUID,
    db: Session = Depends(get_db),
    parent: User = Depends(require_adult),
):
    child = db.get(User, child_id)
    if child is None:
        raise HTTPException(status_code=404)
    # require_parent_of rejects deletion_pending children via status, so check
    # the relationship directly here.
    from app.core.principal import is_parent_of

    if not is_parent_of(db, parent, child_id):
        raise HTTPException(status_code=403, detail="Not a parent of this account.")

    request = db.scalar(
        select(DeletionRequest).where(
            DeletionRequest.user_id == child.id, DeletionRequest.status == "pending"
        )
    )
    if request is None:
        raise HTTPException(status_code=404, detail="No pending deletion.")
    request.status = "cancelled"
    child.status = "active" if consent.has_consent(db, child.id, "account") else "pending_consent"
    db.commit()
    return {"status": "cancelled"}
