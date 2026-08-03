import pytest

from app.services.badges import (
    STARTER_BADGES,
    BadgeRuleError,
    StatsSnapshot,
    evaluate,
)
from app.services.leveling import (
    level_for_xp,
    progress,
    streak_bonus,
    xp_for_level,
)


class TestLeveling:
    def test_new_learner_starts_at_level_one(self):
        assert level_for_xp(0) == 1

    def test_levels_increase_monotonically_with_xp(self):
        levels = [level_for_xp(xp) for xp in range(0, 20000, 250)]
        assert levels == sorted(levels)

    def test_early_levels_come_faster_than_later_ones(self):
        """The curve must front-load progress or new learners stall out."""
        first_gap = xp_for_level(3) - xp_for_level(2)
        later_gap = xp_for_level(12) - xp_for_level(11)
        assert first_gap < later_gap

    def test_xp_for_level_round_trips(self):
        for level in range(1, 25):
            assert level_for_xp(xp_for_level(level)) == level

    def test_negative_xp_is_rejected(self):
        with pytest.raises(ValueError):
            level_for_xp(-1)

    def test_progress_fraction_stays_within_bounds(self):
        for xp in (0, 1, 99, 100, 5000, 100000):
            p = progress(xp)
            assert 0.0 <= p["fraction"] <= 1.0
            assert p["xp_to_next_level"] >= 0
            assert p["level_floor_xp"] <= xp

    def test_streak_bonus_grows_then_caps(self):
        assert streak_bonus(0) == 0
        assert streak_bonus(1) == 0, "a one-day streak isn't a streak yet"
        assert streak_bonus(5) == 10
        assert streak_bonus(1000) == streak_bonus(100), "bonus must cap"


class TestBadgeRules:
    def test_threshold_rules(self):
        stats = StatsSnapshot(longest_streak=7, total_xp=500, level=3)
        assert evaluate({"type": "streak", "gte": 7}, stats)
        assert not evaluate({"type": "streak", "gte": 8}, stats)
        assert evaluate({"type": "total_xp", "gte": 500}, stats)
        assert not evaluate({"type": "level", "gte": 4}, stats)

    def test_accuracy_requires_a_minimum_sample(self):
        # Perfect but only 3 answers — not enough to earn an accuracy badge.
        small = StatsSnapshot(answers_correct=3, answers_total=3)
        rule = {"type": "accuracy", "gte": 0.9, "min_answers": 50}
        assert not evaluate(rule, small)

        big = StatsSnapshot(answers_correct=95, answers_total=100)
        assert evaluate(rule, big)

    def test_accuracy_with_no_answers_does_not_divide_by_zero(self):
        assert not evaluate(
            {"type": "accuracy", "gte": 0.5, "min_answers": 1}, StatsSnapshot()
        )

    def test_composite_all_rule(self):
        rule = {
            "type": "all",
            "rules": [{"type": "streak", "gte": 3}, {"type": "level", "gte": 2}],
        }
        assert evaluate(rule, StatsSnapshot(longest_streak=5, level=2))
        assert not evaluate(rule, StatsSnapshot(longest_streak=5, level=1))

    def test_unknown_rule_type_raises_rather_than_silently_failing(self):
        with pytest.raises(BadgeRuleError):
            evaluate({"type": "phase_of_moon", "gte": 1}, StatsSnapshot())

    def test_rule_missing_threshold_raises(self):
        with pytest.raises(BadgeRuleError):
            evaluate({"type": "streak"}, StatsSnapshot())

    def test_every_starter_badge_rule_is_valid_and_reachable(self):
        """Guards against a typo shipping a badge nobody can ever earn."""
        generous = StatsSnapshot(
            total_xp=100000,
            level=99,
            lessons_done=999,
            answers_correct=9999,
            answers_total=10000,
            current_streak=365,
            longest_streak=365,
        )
        for badge in STARTER_BADGES:
            assert evaluate(badge["rule"], generous), f"{badge['slug']} unreachable"

        nobody = StatsSnapshot()
        for badge in STARTER_BADGES:
            assert not evaluate(badge["rule"], nobody), (
                f"{badge['slug']} awarded to a brand-new learner"
            )

    def test_starter_badge_slugs_are_unique(self):
        slugs = [b["slug"] for b in STARTER_BADGES]
        assert len(slugs) == len(set(slugs))
