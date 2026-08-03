"""Consent state machine.

Runs against a real Postgres schema because the rules depend on constraints and
relationships, not just Python logic.
"""
import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models import metadata
from app.models.core import ConsentAudit, ParentalConsent, User
from app.services.consent import (
    ConsentError,
    attach_evidence,
    granted_scopes,
    has_consent,
    request_consent,
    revoke_consent,
    verify_consent,
)

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="DATABASE_URL not set (Postgres-backed test)"
)

CORE_TABLES = [
    "core.users",
    "core.families",
    "core.family_members",
    "core.parental_consents",
    "core.consent_audit",
    "core.deletion_requests",
]


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(DATABASE_URL)
    with eng.begin() as conn:
        for schema in ("content", "core", "game", "social", "mod", "srs"):
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    metadata.create_all(
        eng, tables=[metadata.tables[t] for t in CORE_TABLES], checkfirst=True
    )
    return eng


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def make_user(db, *, owner=False, status="active", birth_date=None) -> User:
    user = User(
        username=f"u-{uuid.uuid4().hex[:12]}",
        is_owner=owner,
        status=status,
        birth_date=birth_date,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def family(db):
    parent = make_user(db)
    owner = make_user(db, owner=True)
    child = make_user(db, status="pending_consent", birth_date=date(2016, 5, 1))
    return parent, owner, child


class TestRequestConsent:
    def test_creates_pending_rows_and_audits(self, db, family):
        parent, _, child = family
        consents = request_consent(db, child, parent, ["account", "ai_processing"])
        assert {c.scope for c in consents} == {"account", "ai_processing"}
        assert all(c.status == "pending" for c in consents)
        events = db.query(ConsentAudit).filter_by(consent_id=consents[0].id).all()
        assert [e.event for e in events] == ["requested"]

    def test_is_idempotent(self, db, family):
        parent, _, child = family
        request_consent(db, child, parent, ["account"])
        again = request_consent(db, child, parent, ["account"])
        rows = db.query(ParentalConsent).filter_by(child_user_id=child.id).all()
        assert len(rows) == 1
        assert again[0].id == rows[0].id

    def test_unknown_scope_is_rejected(self, db, family):
        parent, _, child = family
        with pytest.raises(ConsentError):
            request_consent(db, child, parent, ["account", "sell_data"])


class TestVerification:
    def test_child_stays_unusable_until_account_consent_is_granted(self, db, family):
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        assert child.status == "pending_consent"

        attach_evidence(db, consent, "consents/form-1.pdf")
        verify_consent(db, consent, owner, approve=True)
        assert consent.status == "granted"
        assert child.status == "active"

    def test_cannot_grant_without_evidence(self, db, family):
        """A parent asserting consent is not verification — there must be a
        signed form on file to inspect."""
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        with pytest.raises(ConsentError, match="no evidence"):
            verify_consent(db, consent, owner, approve=True)
        assert child.status == "pending_consent"

    def test_only_the_owner_can_verify(self, db, family):
        parent, _, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        attach_evidence(db, consent, "consents/form-1.pdf")
        with pytest.raises(ConsentError, match="only the owner"):
            verify_consent(db, consent, parent, approve=True)

    def test_denial_suspends_the_account(self, db, family):
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        attach_evidence(db, consent, "consents/form-1.pdf")
        verify_consent(db, consent, owner, approve=False, note="signature mismatch")
        assert consent.status == "denied"
        assert child.status == "suspended"

    def test_cannot_verify_twice(self, db, family):
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        attach_evidence(db, consent, "consents/form-1.pdf")
        verify_consent(db, consent, owner, approve=True)
        with pytest.raises(ConsentError, match="already granted"):
            verify_consent(db, consent, owner, approve=True)


class TestRevocation:
    def test_parent_can_revoke_at_any_time_and_account_suspends(self, db, family):
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        attach_evidence(db, consent, "consents/form-1.pdf")
        verify_consent(db, consent, owner, approve=True)
        assert child.status == "active"

        revoke_consent(db, consent, parent, reason="changed my mind")
        assert consent.status == "revoked"
        assert consent.revoked_at is not None
        assert child.status == "suspended"

    def test_revoking_a_non_required_scope_leaves_the_account_active(self, db, family):
        parent, owner, child = family
        account, ai = request_consent(db, child, parent, ["account", "ai_processing"])
        for c in (account, ai):
            attach_evidence(db, c, "consents/form-1.pdf")
            verify_consent(db, c, owner, approve=True)
        assert child.status == "active"

        revoke_consent(db, ai, parent)
        assert child.status == "active", "revoking AI consent must not lock them out"
        assert granted_scopes(db, child.id) == {"account"}
        assert not has_consent(db, child.id, "ai_processing")

    def test_revocation_is_idempotent(self, db, family):
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        attach_evidence(db, consent, "k")
        verify_consent(db, consent, owner, approve=True)
        first = revoke_consent(db, consent, parent)
        second = revoke_consent(db, consent, parent)
        assert first.revoked_at == second.revoked_at


class TestAuditTrail:
    def test_every_transition_is_recorded_in_order(self, db, family):
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        attach_evidence(db, consent, "consents/form-1.pdf")
        verify_consent(db, consent, owner, approve=True)
        revoke_consent(db, consent, parent, reason="done")
        db.flush()

        events = [
            row.event
            for row in db.query(ConsentAudit)
            .filter_by(consent_id=consent.id)
            .order_by(ConsentAudit.at, ConsentAudit.id)
            .all()
        ]
        assert events == ["requested", "evidence_attached", "granted", "revoked"]

    def test_audit_records_who_acted(self, db, family):
        parent, owner, child = family
        (consent,) = request_consent(db, child, parent, ["account"])
        attach_evidence(db, consent, "k")
        verify_consent(db, consent, owner, approve=True)
        db.flush()
        granted = (
            db.query(ConsentAudit)
            .filter_by(consent_id=consent.id, event="granted")
            .one()
        )
        assert granted.actor_user_id == owner.id
