"""Self-registration and the age-gate backstop.

The age gate itself is a pure function (see test_ages.py). What matters here is
that the *endpoint* refuses what the gate refuses, because a client that skips
the gate must not be able to create a child account by hand.
"""
import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.core.principal import require_adult
from app.models import metadata
from app.models.core import DeletionRequest, Family, FamilyMember, User
from app.routers.me import (
    cancel_own_deletion,
    get_me,
    register,
    request_own_deletion,
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


def make_user(db, birth_date=None) -> User:
    user = User(username=f"u-{uuid.uuid4().hex[:12]}", birth_date=birth_date)
    db.add(user)
    db.flush()
    return user


def _link_family(db, parent, child) -> None:
    family = Family(name="test", created_by=parent.id)
    db.add(family)
    db.flush()
    db.add(FamilyMember(family_id=family.id, user_id=parent.id, relation="parent"))
    db.add(FamilyMember(family_id=family.id, user_id=child.id, relation="child"))
    db.flush()


def born_years_ago(years: int, days: int = 0) -> str:
    # Server-side "today" is UTC; the local date can be a day behind it.
    today = datetime.now(UTC).date()
    return (
        date(today.year - years, today.month, today.day) + timedelta(days=days)
    ).isoformat()


class TestRegister:
    def test_records_birth_date_and_timezone(self, db):
        user = make_user(db)
        result = register(
            {"birth_date": born_years_ago(30), "timezone": "America/Denver"},
            user=user,
            db=db,
        )
        assert result["bracket"] == "adult"
        assert result["needs_registration"] is False
        assert user.timezone == "America/Denver"

    def test_teen_may_self_register(self, db):
        user = make_user(db)
        assert register({"birth_date": born_years_ago(15)}, user=user, db=db)[
            "bracket"
        ] == "teen"

    def test_under_13_is_refused_and_stores_nothing(self, db):
        user = make_user(db)
        with pytest.raises(HTTPException) as exc:
            register({"birth_date": born_years_ago(9)}, user=user, db=db)
        assert exc.value.status_code == 403
        # The account stays unregistered rather than becoming a child account
        # that nobody consented to.
        assert user.birth_date is None

    def test_turning_13_tomorrow_is_still_a_child(self, db):
        user = make_user(db)
        with pytest.raises(HTTPException) as exc:
            register({"birth_date": born_years_ago(13, days=1)}, user=user, db=db)
        assert exc.value.status_code == 403

    def test_birth_date_is_write_once(self, db):
        user = make_user(db, birth_date=date(1990, 1, 1))
        with pytest.raises(HTTPException) as exc:
            register({"birth_date": born_years_ago(30)}, user=user, db=db)
        assert exc.value.status_code == 409
        assert user.birth_date == date(1990, 1, 1)

    def test_rejects_unknown_timezone(self, db):
        user = make_user(db)
        with pytest.raises(HTTPException) as exc:
            register(
                {"birth_date": born_years_ago(30), "timezone": "Mars/Olympus"},
                user=user,
                db=db,
            )
        assert exc.value.status_code == 400
        assert user.birth_date is None


class TestUnknownAge:
    """An account that never passed the age gate must not inherit adult powers."""

    def test_me_reports_needs_registration(self, db):
        user = make_user(db)
        assert get_me(user=user, db=db)["needs_registration"] is True

    def test_require_adult_refuses_unknown_birth_date(self, db):
        with pytest.raises(HTTPException) as exc:
            require_adult(user=make_user(db))
        assert exc.value.status_code == 403

    def test_require_adult_allows_a_registered_adult(self, db):
        user = make_user(db, birth_date=date(1990, 1, 1))
        assert require_adult(user=user) is user


class TestSelfDeletion:
    """An adult deleting their own account — required in-app by both stores."""

    def test_schedules_a_purge_and_disables_the_account(self, db):
        user = make_user(db, birth_date=date(1990, 1, 1))
        result = request_own_deletion(user=user, db=db)
        assert result["status"] == "pending"
        assert user.status == "deletion_pending"
        request = db.scalar(
            select(DeletionRequest).where(DeletionRequest.user_id == user.id)
        )
        # Self-requested, so both sides of the audit point at the same person.
        assert request.requested_by == user.id
        assert request.purge_after > datetime.now(UTC).date()

    def test_is_idempotent(self, db):
        user = make_user(db, birth_date=date(1990, 1, 1))
        request_own_deletion(user=user, db=db)
        assert request_own_deletion(user=user, db=db)["status"] == "already_pending"
        assert (
            db.scalar(
                select(func.count())
                .select_from(DeletionRequest)
                .where(DeletionRequest.user_id == user.id)
            )
            == 1
        )

    def test_a_parent_with_children_is_refused(self, db):
        parent = make_user(db, birth_date=date(1990, 1, 1))
        child = make_user(db, birth_date=date(2016, 5, 1))
        _link_family(db, parent, child)
        with pytest.raises(HTTPException) as exc:
            request_own_deletion(user=parent, db=db)
        assert exc.value.status_code == 409
        # Nothing happened: a child must never be left without a parent.
        assert parent.status == "active"

    def test_a_parent_may_leave_once_the_children_are_going(self, db):
        parent = make_user(db, birth_date=date(1990, 1, 1))
        child = make_user(db, birth_date=date(2016, 5, 1))
        _link_family(db, parent, child)
        child.status = "deletion_pending"
        db.flush()
        assert request_own_deletion(user=parent, db=db)["status"] == "pending"

    def test_cancelling_restores_the_account(self, db):
        user = make_user(db, birth_date=date(1990, 1, 1))
        request_own_deletion(user=user, db=db)
        assert cancel_own_deletion(user=user, db=db)["status"] == "active"
        assert user.status == "active"
        request = db.scalar(
            select(DeletionRequest).where(DeletionRequest.user_id == user.id)
        )
        assert request.status == "cancelled"

    def test_cancelling_without_a_request_is_a_404(self, db):
        with pytest.raises(HTTPException) as exc:
            cancel_own_deletion(user=make_user(db, birth_date=date(1990, 1, 1)), db=db)
        assert exc.value.status_code == 404

    def test_me_still_answers_while_pending_deletion(self, db):
        """The client needs the status to offer a way back."""
        user = make_user(db, birth_date=date(1990, 1, 1))
        request_own_deletion(user=user, db=db)
        assert get_me(user=user, db=db)["status"] == "deletion_pending"
