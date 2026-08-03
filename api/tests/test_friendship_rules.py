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
    """assert_may_socialize is the single gate on taking part at all.

    There is no chat in the app; "social" means an approved friend seeing your
    progress, and appearing on a leaderboard.
    """

    def _may(self, birth_date, has_social_consent=False) -> bool:
        import app.services.consent as consent_mod
        from app.services.friendships import assert_may_socialize

        original = consent_mod.has_consent
        consent_mod.has_consent = lambda db, uid, scope: has_social_consent
        try:
            assert_may_socialize(None, user(birth_date))
            return True
        except FriendshipError:
            return False
        finally:
            consent_mod.has_consent = original

    def test_adults_may_without_any_consent_record(self):
        assert self._may(date(1990, 1, 1))

    def test_teens_may_without_the_social_scope(self):
        """Teens are gated per-friendship by parental approval, not by an
        up-front scope."""
        assert self._may(date(2011, 1, 1))

    def test_under_13_needs_parental_social_consent(self):
        assert not self._may(date(2018, 1, 1), has_social_consent=False)
        assert self._may(date(2018, 1, 1), has_social_consent=True)

    def test_boundary_the_day_before_turning_13_needs_consent(self):
        from datetime import UTC, datetime, timedelta

        today = datetime.now(UTC).date()
        turns_13_tomorrow = today.replace(year=today.year - 13) + timedelta(days=1)
        assert not self._may(turns_13_tomorrow, has_social_consent=False)

    def test_boundary_on_the_thirteenth_birthday_no_scope_needed(self):
        from datetime import UTC, datetime

        today = datetime.now(UTC).date()
        turns_13_today = today.replace(year=today.year - 13)
        assert self._may(turns_13_today, has_social_consent=False)

    def test_legacy_account_without_a_birth_date_may(self):
        """Rows predating the age gate must not be locked out."""
        assert self._may(None)


class TestSocialConsentScope:
    def test_social_is_a_consent_scope(self):
        """A parent decides up front whether their under-13 child is visible to
        other learners, separately from consenting to the account."""
        from app.services.consent import SCOPES

        assert "social" in SCOPES

    def test_social_consent_is_revocable_like_any_other_scope(self):
        from app.services.consent import REQUIRED_SCOPE

        # Only `account` is required; revoking social must not disable the
        # account, it just removes friends and leaderboards.
        assert REQUIRED_SCOPE == "account"


def test_self_request_is_rejected():
    from app.services.friendships import send_request

    someone = user(date(1990, 1, 1))
    with pytest.raises(FriendshipError, match="yourself"):
        send_request(None, someone, someone)
