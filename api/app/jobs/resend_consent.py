"""Re-issue a parental consent notice.

Needed in production because email delivery fails for ordinary reasons — a
typo'd address, a full mailbox, a spam filter — and a consent request must
never be stranded.

Invoked as: {"task": "resend_consent_notice", "consent_id": "..."}

When SES is not configured (CONSENT_EMAIL_SENDER unset), the link is returned
so a developer can walk the flow locally. This is an operator tool requiring
AWS credentials — it is never reachable from the public API, and the link is
omitted once a sender is configured so it cannot become a way to self-consent.
"""
import os

from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.jobs.consent_followups import _parent_email
from app.models.core import ParentalConsent, User
from app.services import consent_email


def resend_consent_notice(consent_id: str) -> dict:
    with Session(get_engine()) as session:
        consent = session.get(ParentalConsent, consent_id)
        if consent is None:
            raise ValueError(f"unknown consent: {consent_id}")
        if consent.status != "pending":
            return {"status": "skipped", "reason": f"consent is {consent.status}"}

        child = session.get(User, consent.child_user_id)
        parent = session.get(User, consent.parent_user_id)
        email = _parent_email(parent)
        base_url = os.environ.get("PUBLIC_API_URL", "")

        result = consent_email.issue_notice(session, consent, child, email, base_url)
        session.commit()

        out = {
            "status": "ok",
            "scope": consent.scope,
            "delivered": result["delivered"],
            "parent_email_on_file": bool(email),
        }
        if not os.environ.get("CONSENT_EMAIL_SENDER"):
            out["link"] = result["link"]
            out["note"] = "SES not configured; link returned for local testing only"
        return out
