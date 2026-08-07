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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.principal import require_adult
from app.models import metadata
from app.models.core import User
from app.routers.me import get_me, register

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="DATABASE_URL not set (Postgres-backed test)"
)

CORE_TABLES = ["core.users", "core.parental_consents", "core.consent_audit"]


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
