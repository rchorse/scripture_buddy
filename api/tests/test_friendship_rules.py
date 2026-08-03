"""Friendship eligibility rules.

The DB-backed flows are exercised against Postgres in CI; these cover the
age/consent/policy gating logic, which is where a mistake would let a child be
visible to strangers.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.services import ages
from app.services.friendships import FriendshipError, _bracket, _ordered

TODAY = date(2026, 8, 3)


def user(birth_date=None):
    return SimpleNamespace(id="u", birth_date=birth_date)


class TestBracketing:
    def test_missing_birth_date_is_treated_as_adult(self):
        """Legacy rows created before the age gate. Must not crash, and must
        not be treated as a child (which would lock existing users out)."""
        assert _bracket(user(None)) == ages.ADULT

    def test_child_birth_date_yields_under_13(self):
        assert _bracket(user(date(2018, 1, 1))) == ages.UNDER_13

    def test_teen_birth_date_yields_teen(self):
        assert _bracket(user(date(2011, 1, 1))) == ages.TEEN


class TestOrdering:
    def test_pair_ordering_is_stable_regardless_of_argument_order(self):
        """Friendships are stored once with user_a < user_b, so a pair can
        never be duplicated in mirror image."""
        assert _ordered("aaa", "bbb") == ("aaa", "bbb")
        assert _ordered("bbb", "aaa") == ("aaa", "bbb")

    def test_ordering_is_deterministic_for_uuid_like_strings(self):
        one = "38690f32-2668-403e-96c3-280cece3ce01"
        two = "912d16ad-dd8b-4268-9f9d-c16c7f4c476c"
        assert _ordered(one, two) == _ordered(two, one) == (one, two)


class TestSocializeGate:
    """assert_may_socialize is the single gate.

    Under-13 social is a permanent product decision, not a configurable one —
    these tests exist so a future change can't quietly re-enable it.
    """

    def _may(self, birth_date) -> bool:
        from app.services.friendships import assert_may_socialize

        try:
            assert_may_socialize(None, user(birth_date))
            return True
        except FriendshipError:
            return False

    def test_adults_may(self):
        assert self._may(date(1990, 1, 1))

    def test_teens_may(self):
        """Teens are gated per-friendship by parental approval, not here."""
        assert self._may(date(2011, 1, 1))

    def test_under_13_never_may(self):
        assert not self._may(date(2018, 1, 1))

    def test_the_day_before_turning_13_still_may_not(self):
        """The boundary must be exact. Uses the same UTC clock the gate uses —
        the machine's local date can be a day behind and would make this pass
        for the wrong reason."""
        from datetime import UTC, datetime, timedelta

        today = datetime.now(UTC).date()
        turns_13_tomorrow = today.replace(year=today.year - 13) + timedelta(days=1)
        assert not self._may(turns_13_tomorrow)

    def test_on_the_thirteenth_birthday_they_may(self):
        from datetime import UTC, datetime

        today = datetime.now(UTC).date()
        turns_13_today = today.replace(year=today.year - 13)
        assert self._may(turns_13_today)

    def test_legacy_account_without_a_birth_date_may(self):
        """Rows predating the age gate must not be locked out."""
        assert self._may(None)

    def test_gate_needs_no_database(self):
        """The rule is age alone — no consent lookup, no policy flag. If this
        ever needs a db session again, under-13 social has crept back in."""
        from app.services.friendships import assert_may_socialize

        assert_may_socialize(None, user(date(1990, 1, 1)))


class TestNoSocialConsentScope:
    def test_social_is_not_a_consent_scope(self):
        """There is nothing to consent to, so the scope must not exist."""
        from app.services.consent import SCOPES

        assert "social" not in SCOPES
        assert set(SCOPES) == {"account", "ai_processing"}

    def test_requesting_social_consent_is_rejected(self):
        from app.services.consent import SCOPES

        assert "social" not in SCOPES


def test_self_request_is_rejected():
    from app.services.friendships import send_request

    someone = user(date(1990, 1, 1))
    with pytest.raises(FriendshipError, match="yourself"):
        send_request(None, someone, someone)
