from fastapi import APIRouter, Depends

from app.core.auth import TokenIdentity, get_token_identity

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def get_me(identity: TokenIdentity = Depends(get_token_identity)):
    """M0 smoke endpoint: proves the auth round-trip from every client target.
    Grows a DB-backed profile in M1."""
    return {
        "sub": identity.sub,
        "username": identity.username,
        "is_owner": identity.is_owner,
    }
