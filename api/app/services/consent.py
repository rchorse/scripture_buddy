"""Parental consent: request, verify, revoke — with an append-only audit trail.

COPPA requires *verifiable* parental consent before collecting personal
information from a child under 13, separately for distinct uses. The rules
encoded here:

- A child account starts `pending_consent` and cannot be used until the
  `account` scope is granted.
- Each scope is granted and revoked independently.
- Only the owner marks a consent verified, after inspecting the signed form —
  a parent clicking a button is not verification.
- Every transition appends to `consent_audit`, which is never updated or
  deleted.
"""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import ConsentAudit, ParentalConsent, User

# No `social` scope: under-13 accounts have no social surface at all, so
# there is nothing for a parent to consent to. See services/friendships.py.
SCOPES = ("account", "ai_processing")
# Without this scope the child account cannot be used at all.
REQUIRED_SCOPE = "account"


class ConsentError(ValueError):
    pass


def _audit(
    db: Session, consent: ParentalConsent, event: str, actor_id=None, **detail
) -> None:
    db.add(
        ConsentAudit(
            consent_id=consent.id,
            event=event,
            actor_user_id=actor_id,
            detail=detail or {},
        )
    )


def request_consent(
    db: Session,
    child: User,
    parent: User,
    scopes: list[str] | None = None,
    method: str = "signed_form",
) -> list[ParentalConsent]:
    """Create pending consent rows for a newly created child account."""
    scopes = scopes or [REQUIRED_SCOPE]
    unknown = set(scopes) - set(SCOPES)
    if unknown:
        raise ConsentError(f"unknown consent scopes: {sorted(unknown)}")

    created = []
    for scope in scopes:
        existing = db.scalar(
            select(ParentalConsent).where(
                ParentalConsent.child_user_id == child.id,
                ParentalConsent.scope == scope,
            )
        )
        if existing is not None:
            created.append(existing)
            continue
        consent = ParentalConsent(
            child_user_id=child.id,
            parent_user_id=parent.id,
            scope=scope,
            method=method,
            status="pending",
        )
        db.add(consent)
        db.flush()
        _audit(db, consent, "requested", actor_id=parent.id, scope=scope, method=method)
        created.append(consent)
    return created


def attach_evidence(
    db: Session, consent: ParentalConsent, s3_key: str, actor_id=None
) -> ParentalConsent:
    """Record the uploaded signed form. Does NOT grant consent."""
    if consent.status == "revoked":
        raise ConsentError("cannot attach evidence to a revoked consent")
    consent.evidence_s3_key = s3_key
    _audit(db, consent, "evidence_attached", actor_id=actor_id, s3_key=s3_key)
    return consent


def verify_consent(
    db: Session, consent: ParentalConsent, owner: User, approve: bool, note: str = ""
) -> ParentalConsent:
    """Owner decision after inspecting the signed form.

    This is the verifiable step. Only an owner may call it, and only against a
    consent that has evidence attached — otherwise there is nothing to verify.
    """
    if not owner.is_owner:
        raise ConsentError("only the owner can verify consent")
    if consent.status in ("granted", "revoked"):
        raise ConsentError(f"consent is already {consent.status}")
    if approve and not consent.evidence_s3_key:
        raise ConsentError("cannot grant consent with no evidence on file")

    now = datetime.now(UTC)
    if approve:
        consent.status = "granted"
        consent.granted_at = now
        consent.verified_by = owner.id
        _audit(db, consent, "granted", actor_id=owner.id, note=note)
    else:
        consent.status = "denied"
        _audit(db, consent, "denied", actor_id=owner.id, note=note)

    _sync_child_status(db, consent)
    return consent


def revoke_consent(
    db: Session, consent: ParentalConsent, actor: User, reason: str = ""
) -> ParentalConsent:
    """A parent withdrawing consent. Always permitted, at any time."""
    if consent.status == "revoked":
        return consent
    consent.status = "revoked"
    consent.revoked_at = datetime.now(UTC)
    _audit(db, consent, "revoked", actor_id=actor.id, reason=reason)
    _sync_child_status(db, consent)
    return consent


def _sync_child_status(db: Session, consent: ParentalConsent) -> None:
    """Keep the child's account status aligned with the required scope."""
    if consent.scope != REQUIRED_SCOPE:
        return
    child = db.get(User, consent.child_user_id)
    if child is None:
        return
    if consent.status == "granted":
        if child.status == "pending_consent":
            child.status = "active"
    elif consent.status in ("revoked", "denied"):
        # Losing account consent suspends the account immediately.
        child.status = "suspended"


def granted_scopes(db: Session, child_user_id) -> set[str]:
    return {
        row.scope
        for row in db.scalars(
            select(ParentalConsent).where(
                ParentalConsent.child_user_id == child_user_id,
                ParentalConsent.status == "granted",
            )
        )
    }


def has_consent(db: Session, child_user_id, scope: str) -> bool:
    return scope in granted_scopes(db, child_user_id)
