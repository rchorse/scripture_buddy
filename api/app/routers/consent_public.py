"""The parent-facing consent link.

Deliberately unauthenticated: a parent clicking a link in their email is not
signed in, and requiring them to sign in first would defeat the point. Security
comes from the token — single-use, 72-hour expiry, stored only as a hash.

Returns HTML because it is opened in a mail client's browser.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.core import User
from app.services.consent import ConsentError
from app.services.consent_email import SCOPE_LABELS, confirm_by_token

router = APIRouter(prefix="/consent", tags=["consent"])

_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ScriptureBuddy — Parental consent</title>
<style>
 body {{ font-family: system-ui, sans-serif; background:#f6f8f4; color:#1c231b;
        margin:0; padding:2rem; }}
 .card {{ background:#fff; max-width:520px; margin:3rem auto; padding:2rem;
         border-radius:12px; box-shadow:0 1px 4px rgb(0 0 0 / .08); }}
 h1 {{ font-size:1.4rem; margin-top:0; }}
 .ok {{ color:#2e7d32; }} .bad {{ color:#b3261e; }}
 ul {{ line-height:1.7; }}
</style></head>
<body><div class="card">{body}</div></body></html>
"""


def _page(body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(body=body), status_code=status)


@router.get("/confirm", response_class=HTMLResponse)
def confirm(token: str = "", db: Session = Depends(get_db)):
    if not token:
        return _page("<h1 class='bad'>Missing link</h1><p>This link is incomplete.</p>", 400)
    try:
        consent = confirm_by_token(db, token)
    except ConsentError as exc:
        db.rollback()
        return _page(f"<h1 class='bad'>Consent not recorded</h1><p>{exc}</p>", 400)

    child = db.get(User, consent.child_user_id)
    db.commit()
    what = SCOPE_LABELS.get(consent.scope, consent.scope)
    return _page(
        f"""<h1 class="ok">Thank you — consent recorded</h1>
<p>You have consented to let <strong>{child.username if child else "your child"}</strong>
{what} on ScriptureBuddy. Their account is now active.</p>
<p>You remain in control:</p>
<ul>
  <li>Withdraw consent at any time from the Family screen — this disables the account immediately.</li>
  <li>Ask us to delete their data at any time.</li>
  <li>We never collect an email, phone number, real name, or location for a child.</li>
</ul>
<p>We will send you a confirmation email shortly. If you did not make this
request, withdraw consent from that email and the account will be disabled.</p>"""
    )
