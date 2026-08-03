"""Display-name screening.

Display names are the only free text one learner sees from another, and for an
under-13 account they are visible to unrelated learners in a league cohort — so
the fail-closed behaviour matters more than the happy path.
"""
from types import SimpleNamespace

from app.services.name_moderation import (
    FLAGGED,
    OK,
    PENDING,
    basic_checks,
    public_name,
    screen,
)


class TestBasicChecks:
    def test_accepts_an_ordinary_nickname(self):
        assert basic_checks("BraveVoyager") is None

    def test_rejects_empty_and_whitespace(self):
        assert basic_checks("") is not None
        assert basic_checks("   ") is not None

    def test_rejects_overlong_names(self):
        assert basic_checks("x" * 25) is not None

    def test_rejects_email_like_names(self):
        assert basic_checks("sam@example.com") is not None

    def test_rejects_phone_numbers(self):
        assert basic_checks("call 5551234567") is not None

    def test_allows_a_few_digits(self):
        """Nicknames like 'Nephi3' or 'Runner42' are fine."""
        assert basic_checks("Nephi3") is None
        assert basic_checks("Runner42") is None

    def test_rejects_urls(self):
        assert basic_checks("https://spam.example") is not None
        assert basic_checks("www.spam.example") is not None


class TestFailClosed:
    def test_screening_failure_yields_pending_not_ok(self, monkeypatch):
        """If the check is unavailable for ANY reason — network, credentials,
        a bad response — the name must NOT be shown. A missing nickname is a
        far smaller harm than publishing a child's real name."""
        import app.services.name_moderation as mod

        def explode():
            raise RuntimeError("secrets manager unreachable")

        monkeypatch.setattr(mod, "_api_key", explode)
        result = screen("AnyName", is_child=True)
        assert result["status"] == PENDING
        assert result["status"] != OK

    def test_failure_is_pending_for_adults_too(self, monkeypatch):
        import app.services.name_moderation as mod

        monkeypatch.setattr(
            mod, "_api_key", lambda: (_ for _ in ()).throw(RuntimeError("down"))
        )
        assert screen("AnyName", is_child=False)["status"] == PENDING

    def test_basic_rejections_do_not_need_the_model(self, monkeypatch):
        """Deterministic rejections must work even with no API access."""
        import app.services.name_moderation as mod

        def explode():
            raise RuntimeError("should not be called")

        monkeypatch.setattr(mod, "_api_key", explode)
        assert screen("sam@example.com", is_child=True)["status"] == FLAGGED


class TestPublicName:
    def test_cleared_display_name_is_shown(self):
        user = SimpleNamespace(
            display_name="BraveVoyager", display_name_status=OK, username="bv-2016"
        )
        assert public_name(user) == "BraveVoyager"

    def test_flagged_name_falls_back_to_username(self):
        user = SimpleNamespace(
            display_name="Sam Smith, Lincoln Elementary",
            display_name_status=FLAGGED,
            username="bv-2016",
        )
        assert public_name(user) == "bv-2016"

    def test_pending_name_is_not_shown(self):
        """A name awaiting screening must not leak while it waits."""
        user = SimpleNamespace(
            display_name="Unscreened",
            display_name_status=PENDING,
            username="bv-2016",
        )
        assert public_name(user) == "bv-2016"

    def test_missing_display_name_falls_back_to_username(self):
        user = SimpleNamespace(
            display_name="", display_name_status=OK, username="bv-2016"
        )
        assert public_name(user) == "bv-2016"


class TestPromptComposition:
    def test_child_prompt_includes_personal_information_rules(self):
        """The under-13 screen must look for identifying details, not just
        offensive language."""
        from app.services.name_moderation import _CHILD_RULES

        for signal in ("full name", "school", "phone number", "identify or locate"):
            assert signal in _CHILD_RULES.lower() or signal in _CHILD_RULES

    def test_all_age_rules_cover_impersonation(self):
        from app.services.name_moderation import _ALL_AGES_RULES

        assert "impersonat" in _ALL_AGES_RULES.lower()
