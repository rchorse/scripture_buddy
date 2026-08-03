"""Email-plus verifiable parental consent.

The FTC allows a lighter consent method for operators that do not disclose
children's personal information to third parties or make it publicly
available. ScriptureBuddy qualifies: no chat, no ads SDKs, nothing sold or
shared, and AWS/Anthropic act as service providers.

The "plus" is the second step: after the parent consents via a one-time link,
a delayed confirmation email gives them an independent chance to notice and
revoke if they did not in fact consent.

Tokens are single-use, time-limited, and stored only as a SHA-256 hash, so a
database leak cannot be replayed to grant consent.
"""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import ParentalConsent, User
from app.services import mailer
from app.services.consent import _audit

TOKEN_TTL_HOURS = 72
# Delay before the confirmatory "you consented" email — the "plus" step.
FOLLOWUP_DELAY_HOURS = 24

SCOPE_LABELS = {
    "account": "create and use a ScriptureBuddy account",
    "ai_processing": "have AI help check their answers and generate practice questions",
}


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_notice(
    db: Session,
    consent: ParentalConsent,
    child: User,
    parent_email: str,
    base_url: str,
) -> dict:
    """Generate a one-time link and email the consent notice to the parent."""
    raw_token = secrets.token_urlsafe(32)
    consent.confirm_token_hash = hash_token(raw_token)
    consent.token_expires_at = datetime.now(UTC) + timedelta(hours=TOKEN_TTL_HOURS)
    consent.notice_sent_at = datetime.now(UTC)
    consent.method = "email_plus"

    link = f"{base_url}/v1/consent/confirm?token={raw_token}"
    what = SCOPE_LABELS.get(consent.scope, consent.scope)
    subject = f"Please confirm consent for {child.username} on ScriptureBuddy"
    text = f"""You asked to create a ScriptureBuddy account for {child.username}.

Because they are under 13, US law (COPPA) requires us to confirm that a parent
or guardian consents before the account can be used.

You are being asked to consent to let them {what}.

What we collect for a child account: a username you choose, their birth date
(used only to apply the right protections), their timezone, and their progress
in the app. We do not collect an email address, phone number, real name, or
location for a child. We do not show ads, and we never sell or share their
information.

To give consent, open this link within {TOKEN_TTL_HOURS} hours:

{link}

If you did not request this, you can ignore this email — without your consent
the account stays locked and we will delete it.

You can withdraw consent at any time from the Family screen in the app, which
immediately disables the account, and you can ask us to delete their data.
"""
    result = mailer.send(parent_email, subject, text)
    _audit(
        db,
        consent,
        "notice_sent",
        actor_id=consent.parent_user_id,
        delivered=result["delivered"],
        to=_mask(parent_email),
    )
    return {**result, "link": link, "expires_at": consent.token_expires_at.isoformat()}


def confirm_by_token(db: Session, raw_token: str) -> ParentalConsent:
    """Grant consent from a one-time link. Raises on bad or expired tokens."""
    from app.services.consent import ConsentError, _sync_child_status

    token_hash = hash_token(raw_token)
    consent = db.scalar(
        select(ParentalConsent).where(ParentalConsent.confirm_token_hash == token_hash)
    )
    if consent is None:
        raise ConsentError("This consent link is not valid.")
    if consent.status == "granted":
        return consent  # already confirmed; clicking twice is harmless
    if consent.status == "revoked":
        raise ConsentError("Consent for this account was withdrawn.")
    if consent.token_expires_at and datetime.now(UTC) > consent.token_expires_at.replace(
        tzinfo=UTC
    ):
        raise ConsentError("This consent link has expired. Please request a new one.")

    now = datetime.now(UTC)
    consent.status = "granted"
    consent.granted_at = now
    # Burn the token so the link cannot be replayed.
    consent.confirm_token_hash = None
    consent.token_expires_at = None
    _audit(db, consent, "granted", actor_id=consent.parent_user_id, via="email_plus")
    _sync_child_status(db, consent)
    return consent


def due_for_followup(db: Session, now: datetime | None = None) -> list[ParentalConsent]:
    """Consents granted long enough ago to send the confirmatory email."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=FOLLOWUP_DELAY_HOURS)
    return list(
        db.scalars(
            select(ParentalConsent).where(
                ParentalConsent.status == "granted",
                ParentalConsent.granted_at.isnot(None),
                ParentalConsent.granted_at <= cutoff,
                ParentalConsent.followup_sent_at.is_(None),
            )
        )
    )


def send_followup(
    db: Session, consent: ParentalConsent, child: User, parent_email: str, base_url: str
) -> dict:
    """The 'plus' step: an independent chance to notice and undo."""
    what = SCOPE_LABELS.get(consent.scope, consent.scope)
    when = consent.granted_at.strftime("%d %B %Y") if consent.granted_at else "recently"
    subject = f"You consented for {child.username} on ScriptureBuddy"
    text = f"""This is a confirmation, not a request.

On {when} we recorded your consent to let {child.username} {what} on
ScriptureBuddy, and their account is now active.

If that was you, there is nothing to do.

If you did NOT give this consent, sign in and open the Family screen to
withdraw it immediately, or reply to this email and we will disable the
account and delete their data.

You can withdraw consent at any time.
"""
    result = mailer.send(parent_email, subject, text)
    consent.followup_sent_at = datetime.now(UTC)
    _audit(
        db,
        consent,
        "followup_sent",
        actor_id=None,
        delivered=result["delivered"],
        to=_mask(parent_email),
    )
    return result


def _mask(email: str) -> str:
    """Audit rows record that we emailed, not the address itself."""
    if "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    return f"{name[:2]}***@{domain}"
