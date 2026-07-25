"""Cognito JWT verification dependency.

Child accounts are username-only (no email), so email claims are optional.
Age bracket and family relationships are resolved from the database by the
principal layer, never from client-supplied data.
"""
import os
import time
from functools import lru_cache
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode
from pydantic import BaseModel

_bearer = HTTPBearer()

USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
USER_POOL_CLIENT_ID = os.environ.get("USER_POOL_CLIENT_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")

JWKS_URL = (
    f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
)

OWNER_GROUP = "owner"


class TokenIdentity(BaseModel):
    sub: str
    username: str = ""
    email: str = ""
    groups: list[str] = []

    @property
    def is_owner(self) -> bool:
        return OWNER_GROUP in self.groups


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch Cognito JWKS once per Lambda instance (cached in memory)."""
    response = httpx.get(JWKS_URL, timeout=5)
    response.raise_for_status()
    return response.json()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _verify_token(token: str) -> dict[str, Any]:
    jwks = _get_jwks()
    headers = jwt.get_unverified_headers(token)
    kid = headers.get("kid")

    key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if key_data is None:
        raise _unauthorized("Unknown signing key")

    public_key = jwk.construct(key_data)
    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode())

    if not public_key.verify(message.encode(), decoded_sig):
        raise _unauthorized("Invalid token signature")

    claims = jwt.get_unverified_claims(token)

    if claims.get("exp") is None or time.time() >= float(claims["exp"]):
        raise _unauthorized("Token expired")

    if claims.get("aud") != USER_POOL_CLIENT_ID and claims.get("client_id") != USER_POOL_CLIENT_ID:
        raise _unauthorized("Token audience mismatch")

    if claims.get("token_use") not in ("id", "access"):
        raise _unauthorized("Invalid token_use")

    return claims


async def get_token_identity(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TokenIdentity:
    try:
        claims = _verify_token(credentials.credentials)
    except JWTError as e:
        raise _unauthorized(str(e))

    return TokenIdentity(
        sub=claims["sub"],
        username=claims.get("cognito:username", claims.get("username", "")),
        email=claims.get("email", ""),
        groups=claims.get("cognito:groups", []),
    )
