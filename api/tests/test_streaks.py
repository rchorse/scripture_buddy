"""Streak behaviour across timezones and DST.

A streak that breaks because of a timezone bug is worse than no streak at all,
so the boundary cases get more coverage than the happy path.
"""
from datetime import UTC, date, datetime, timedelta

import pytest

from app.services.streaks import (
    StreakState,
    is_at_risk,
    local_date,
    record_activity,
    roll_over,
    zone_for,
)


class TestLocalDate:
    def test_auckland_is_already_tomorrow_relative_to_utc(self):
        # 2026-08-01 22:00 UTC is 2026-08-02 10:00 in Auckland.
        now = datetime(2026, 8, 1, 22, 0, tzinfo=UTC)
        assert local_date(now, "Pacific/Auckland") == date(2026, 8, 2)
        assert local_date(now, "UTC") == date(2026, 8, 1)

    def test_los_angeles_is_still_yesterday_relative_to_utc(self):
        # 2026-08-02 03:00 UTC is 2026-08-01 20:00 in Los Angeles.
        now = datetime(2026, 8, 2, 3, 0, tzinfo=UTC)
        assert local_date(now, "America/Los_Angeles") == date(2026, 8, 1)

    def test_unknown_timezone_falls_back_to_utc_instead_of_raising(self):
        now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
        assert local_date(now, "Mars/Olympus_Mons") == date(2026, 8, 1)
        assert local_date(now, None) == date(2026, 8, 1)
        assert zone_for("nonsense").key == "UTC"

    def test_naive_datetime_is_rejected(self):
        with pytest.raises(ValueError):
            local_date(datetime(2026, 8, 1, 12, 0), "UTC")  # noqa: DTZ001 — the point

    def test_dst_spring_forward_still_yields_one_date_per_day(self):
        # US DST begins 2026-03-08. Walk 48 hours across the transition and
        # confirm each local day appears and no day is skipped.
        seen = []
        start = datetime(2026, 3, 7, 8, 0, tzinfo=UTC)
        for hour in range(0, 72, 6):
            d = local_date(start + timedelta(hours=hour), "America/New_York")
            if d not in seen:
                seen.append(d)
        assert seen == [date(2026, 3, 7), date(2026, 3, 8), date(2026, 3, 9)]


class TestRecordActivity:
    def test_first_activity_starts_a_streak_of_one(self):
        state = record_activity(StreakState(), date(2026, 8, 1))
        assert state.current == 1
        assert state.longest == 1

    def test_consecutive_days_increment(self):
        state = StreakState()
        for day in range(1, 6):
            state = record_activity(state, date(2026, 8, day))
        assert state.current == 5
        assert state.longest == 5

    def test_twice_in_one_day_counts_once(self):
        state = record_activity(StreakState(), date(2026, 8, 1))
        again = record_activity(state, date(2026, 8, 1))
        assert again.current == 1
        assert again is state

    def test_gap_resets_to_one_but_keeps_longest(self):
        state = StreakState()
        for day in range(1, 8):
            state = record_activity(state, date(2026, 8, day))
        lapsed = record_activity(state, date(2026, 8, 20))
        assert lapsed.current == 1
        assert lapsed.longest == 7

    def test_freeze_bridges_a_missed_day(self):
        state = StreakState(
            current=5,
            longest=5,
            last_active_local_date=date(2026, 8, 1),
            freeze_used_dates=(date(2026, 8, 2),),
        )
        resumed = record_activity(state, date(2026, 8, 3))
        assert resumed.current == 6, "a frozen day should not break the chain"

    def test_freeze_does_not_bridge_an_uncovered_gap(self):
        state = StreakState(
            current=5,
            last_active_local_date=date(2026, 8, 1),
            freeze_used_dates=(date(2026, 8, 2),),
        )
        # 8-03 was missed too and was never frozen.
        resumed = record_activity(state, date(2026, 8, 4))
        assert resumed.current == 1


class TestRollOver:
    def test_practised_yesterday_keeps_the_streak(self):
        state = StreakState(current=3, last_active_local_date=date(2026, 8, 1))
        rolled, outcome = roll_over(state, date(2026, 8, 2))
        assert outcome == "kept"
        assert rolled.current == 3

    def test_missed_day_consumes_a_freeze(self):
        state = StreakState(
            current=3, last_active_local_date=date(2026, 8, 1), freezes_available=1
        )
        rolled, outcome = roll_over(state, date(2026, 8, 3))
        assert outcome == "frozen"
        assert rolled.current == 3
        assert rolled.freezes_available == 0
        assert date(2026, 8, 2) in rolled.freeze_used_dates

    def test_missed_day_without_a_freeze_resets(self):
        state = StreakState(
            current=9, last_active_local_date=date(2026, 8, 1), freezes_available=0
        )
        rolled, outcome = roll_over(state, date(2026, 8, 3))
        assert outcome == "reset"
        assert rolled.current == 0

    def test_rollover_is_idempotent_within_a_day(self):
        """The hourly job may see the same learner twice; a second pass must
        not consume another freeze."""
        state = StreakState(
            current=3, last_active_local_date=date(2026, 8, 1), freezes_available=1
        )
        first, outcome1 = roll_over(state, date(2026, 8, 3))
        second, outcome2 = roll_over(first, date(2026, 8, 3))
        assert outcome1 == "frozen"
        assert outcome2 == "noop"
        assert second.freezes_available == 0

    def test_zero_streak_is_a_noop(self):
        state = StreakState(current=0)
        rolled, outcome = roll_over(state, date(2026, 8, 2))
        assert outcome == "noop"
        assert rolled.current == 0


class TestAtRisk:
    def test_at_risk_when_streak_alive_and_not_practised_today(self):
        state = StreakState(current=4, last_active_local_date=date(2026, 8, 1))
        assert is_at_risk(state, date(2026, 8, 2))

    def test_not_at_risk_after_practising_today(self):
        state = StreakState(current=4, last_active_local_date=date(2026, 8, 2))
        assert not is_at_risk(state, date(2026, 8, 2))

    def test_no_streak_is_not_at_risk(self):
        assert not is_at_risk(StreakState(current=0), date(2026, 8, 2))
