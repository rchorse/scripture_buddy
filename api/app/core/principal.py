"""Resolve the authenticated token to a core.users row, provisioning on first
contact. Age/family/role logic attaches here in M5."""
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import TokenIdentity, get_token_identity
from app.core.db import get_db
from app.models.core import User


def get_current_user(
    identity: TokenIdentity = Depends(get_token_identity),
    db: Session = Depends(get_db),
) -> User:
    user = db.scalar(select(User).where(User.cognito_sub == identity.sub))
    if user is None:
        user = User(
            cognito_sub=identity.sub,
            username=identity.username or identity.sub,
            display_name=identity.username or "",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
