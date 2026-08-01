"""Admin session auth: server-side Cognito login, JWT-in-cookie session.

The admin UI is owner-only (Cognito group `owner`). Login posts credentials
server-side to Cognito (USER_PASSWORD_AUTH); the resulting ID token becomes an
HttpOnly session cookie, re-verified by the same JWKS path as the API on every
admin request.
"""
import os

import boto3
from fastapi import HTTPException, Request, status

from app.core.auth import OWNER_GROUP, _verify_token

COOKIE_NAME = "sb_admin"


def cognito_login(username: str, password: str) -> str:
    """Return an ID token for valid owner credentials, else raise 401."""
    client = boto3.client(
        "cognito-idp", region_name=os.environ.get("AWS_REGION", "us-west-2")
    )
    try:
        result = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=os.environ["USER_POOL_CLIENT_ID"],
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
    except client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
    return result["AuthenticationResult"]["IdToken"]


def require_owner(request: Request) -> dict:
    """Dependency for admin routes: valid session cookie + owner group."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": os.environ.get("URL_PREFIX", "") + "/admin/login"},
        )
    try:
        claims = _verify_token(token)
    except Exception:  # noqa: BLE001 — any token failure means "not signed in"
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": os.environ.get("URL_PREFIX", "") + "/admin/login"},
        )
    if OWNER_GROUP not in claims.get("cognito:groups", []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
    return claims
