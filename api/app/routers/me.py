from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.principal import bracket_of, get_current_user
from app.models.core import User
from app.services import ages, consent

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def get_me(
    # Declared before `db` on purpose: FastAPI resolves dependencies in order,
    # so an unauthenticated request is rejected before anything opens a
    # connection.
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The signed-in user's profile.

    `needs_registration` drives the client: a self-provisioned row has no
    birth_date, and until it does we cannot tell an adult from a 14-year-old.
    The client must send the age gate before anything else.
    """
    return {
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "is_owner": user.is_owner,
        "status": user.status,
        "timezone": user.timezone,
        "bracket": bracket_of(user),
        "needs_registration": user.birth_date is None,
        "consents": sorted(consent.granted_scopes(db, user.id)),
    }


@router.post("/register")
def register(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record birth date and timezone for an account that just signed itself up.

    Write-once: birth_date is the single source of age truth, so letting it be
    edited would let a minor promote themselves out of their bracket. Changing
    it afterwards is a support action, not a self-service one.

    Under-13s are rejected here as a backstop. The age gate already refuses to
    send them to a signup form, but this endpoint is what actually enforces it
    — a client that skipped the gate cannot register a child this way.
    """
    if user.birth_date is not None:
        raise HTTPException(
            status_code=409, detail="This account has already completed registration."
        )

    raw = body.get("birth_date")
    if not raw:
        raise HTTPException(status_code=400, detail="birth_date is required")
    try:
        birth_date = ages.validate_birth_date(
            date.fromisoformat(raw), datetime.now(UTC).date()
        )
    except (ValueError, ages.InvalidBirthDate) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid birth date: {exc}")

    bracket = ages.bracket_for(birth_date, datetime.now(UTC).date())
    if not ages.can_self_register(bracket):
        # Nothing is stored: the row keeps its null birth_date and the account
        # stays unusable rather than becoming a child account without consent.
        raise HTTPException(
            status_code=403,
            detail="A parent or guardian needs to create this account for you.",
        )

    timezone = body.get("timezone") or "UTC"
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=400, detail=f"Unknown timezone: {timezone}")

    user.birth_date = birth_date
    user.timezone = timezone
    if body.get("display_name"):
        user.display_name = str(body["display_name"])[:40]
    db.commit()
    db.refresh(user)

    return {
        "user_id": str(user.id),
        "username": user.username,
        "bracket": bracket,
        "status": user.status,
        "needs_registration": False,
    }
