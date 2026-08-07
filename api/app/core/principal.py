"""Resolve the authenticated token to a user, plus the authorization guards.

Age bracket and family relationships are always resolved from the database
here — never trusted from the client. Every COPPA-relevant decision in the API
routes through one of the `require_*` dependencies below.
"""
from datetime import UTC, date, datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import TokenIdentity, get_token_identity
from app.core.db import get_db
from app.models.core import FamilyMember, User
from app.services import ages, consent


def get_current_user(
    identity: TokenIdentity = Depends(get_token_identity),
    db: Session = Depends(get_db),
) -> User:
    """The signed-in user, provisioned on first contact.

    Self-provisioning only ever creates an ADULT-shaped row: a child account is
    created by a parent ahead of time and claimed at first sign-in, so a child
    can never bootstrap themselves past the age gate.
    """
    user = db.scalar(select(User).where(User.cognito_sub == identity.sub))
    if user is None:
        # A parent-created child claims their pre-made row by username.
        pending = db.scalar(
            select(User).where(
                User.username == identity.username, User.cognito_sub.is_(None)
            )
        )
        if pending is not None:
            pending.cognito_sub = identity.sub
            db.commit()
            db.refresh(pending)
            user = pending
        else:
            user = User(
                cognito_sub=identity.sub,
                username=identity.username or identity.sub,
                display_name=identity.username or "",
                is_owner=identity.is_owner,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    # The Cognito group is the source of truth for ownership; keep the row in
    # sync so services can check it without re-reading the token.
    if user.is_owner != identity.is_owner:
        user.is_owner = identity.is_owner
        db.commit()

    if user.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is suspended pending parental consent.",
        )
    if user.status == "pending_consent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A parent must complete consent before this account can be used.",
        )
    if user.status == "deletion_pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is scheduled for deletion.",
        )
    return user


def bracket_of(user: User, today: date | None = None) -> str:
    """Age bracket, derived from birth_date. Unknown ages are treated as
    adult only for legacy rows created before the age gate existed."""
    if user.birth_date is None:
        return ages.ADULT
    return ages.bracket_for(user.birth_date, today or datetime.now(UTC).date())


def require_adult(user: User = Depends(get_current_user)) -> User:
    """Guard for adult-only powers — chiefly acting as a parent.

    An account that has not been through the age gate has no birth_date, and
    `bracket_of` optimistically calls that adult so legacy rows keep working.
    That default must not extend here: otherwise anyone who signs up and simply
    never registers would hold parental powers over child accounts. Unknown age
    is refused, and the client sends them back through registration.
    """
    if user.birth_date is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please finish setting up your account before doing this.",
        )
    if bracket_of(user) != ages.ADULT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is only available to adults.",
        )
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    if not user.is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
    return user


def is_parent_of(db: Session, parent: User, child_user_id) -> bool:
    """True when both are in the same family and the roles line up."""
    parent_families = {
        row.family_id
        for row in db.scalars(
            select(FamilyMember).where(
                FamilyMember.user_id == parent.id, FamilyMember.relation == "parent"
            )
        )
    }
    if not parent_families:
        return False
    return (
        db.scalar(
            select(FamilyMember).where(
                FamilyMember.user_id == child_user_id,
                FamilyMember.relation == "child",
                FamilyMember.family_id.in_(parent_families),
            )
        )
        is not None
    )


def require_parent_of(db: Session, parent: User, child_user_id) -> User:
    """Guard for any parent-acting-on-child endpoint.

    Parental authority ends at 18 — an adult child's data is their own.
    """
    if not is_parent_of(db, parent, child_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a parent of this account.",
        )
    child = db.get(User, child_user_id)
    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if bracket_of(child) == ages.ADULT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account holder is now an adult and manages their own account.",
        )
    return child


def require_consent(db: Session, user: User, scope: str) -> None:
    """Block a feature when a child lacks consent for that specific use."""
    if bracket_of(user) != ages.UNDER_13:
        return
    if not consent.has_consent(db, user.id, scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Parental consent for '{scope}' is required.",
        )
