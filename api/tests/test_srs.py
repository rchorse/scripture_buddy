"""Scheduler behaviour at fixed clocks.

These are the properties that must hold for spaced repetition to work at all;
if one breaks, learners get cards at the wrong time and retention suffers
silently.
"""
from datetime import UTC, datetime, timedelta

import pytest

from app.services.srs import (
    AGAIN,
    EASY,
    GOOD,
    HARD,
    MAX_DIFFICULTY,
    MIN_DIFFICULTY,
    RETENTION_TARGET,
    CardState,
    interval_for_stability,
    new_card,
    retrievability,
    review,
)

T0 = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def days_until_due(card: CardState, now: datetime) -> float:
    return (card.due_at - now).total_seconds() / 86400


def test_rating_must_be_valid():
    with pytest.raises(ValueError):
        review(new_card(T0), 5, T0)


def test_first_review_intervals_increase_with_rating():
    intervals = [
        days_until_due(review(new_card(T0), rating, T0), T0)
        for rating in (AGAIN, HARD, GOOD, EASY)
    ]
    assert intervals == sorted(intervals), intervals
    # A failed first attempt must come back fast.
    assert intervals[0] <= 0.5


def test_repeated_good_reviews_grow_the_interval():
    card = new_card(T0)
    now = T0
    intervals = []
    for _ in range(5):
        card = review(card, GOOD, now)
        interval = days_until_due(card, now)
        intervals.append(interval)
        now = card.due_at
    assert intervals == sorted(intervals), intervals
    # Five successful reviews should reach a genuinely long interval.
    assert intervals[-1] > 30, intervals


def test_again_after_success_causes_a_lapse_and_shrinks_stability():
    card = new_card(T0)
    now = T0
    for _ in range(3):
        card = review(card, GOOD, now)
        now = card.due_at
    before = card.stability
    lapsed = review(card, AGAIN, now)
    assert lapsed.state == "lapsed"
    assert lapsed.lapses == 1
    assert lapsed.stability < before
    assert days_until_due(lapsed, now) <= 0.5


def test_difficulty_stays_in_range_under_adversarial_input():
    card = new_card(T0)
    now = T0
    for rating in [AGAIN] * 20:
        card = review(card, rating, now)
        now = card.due_at
        assert MIN_DIFFICULTY <= card.difficulty <= MAX_DIFFICULTY
    for rating in [EASY] * 20:
        card = review(card, rating, now)
        now = card.due_at
        assert MIN_DIFFICULTY <= card.difficulty <= MAX_DIFFICULTY


def test_harder_cards_get_shorter_intervals_than_easy_ones():
    """Two cards, same history length, different ratings — the struggled-with
    card must come back sooner."""
    easy_card, hard_card = new_card(T0), new_card(T0)
    now = T0
    for _ in range(3):
        easy_card = review(easy_card, EASY, now)
        hard_card = review(hard_card, HARD, now)
        now = min(easy_card.due_at, hard_card.due_at)
    assert hard_card.stability < easy_card.stability


def test_retrievability_decays_to_target_at_the_scheduled_interval():
    for stability in (1.0, 7.0, 60.0, 365.0):
        interval = interval_for_stability(stability)
        assert retrievability(stability, interval) == pytest.approx(
            RETENTION_TARGET, abs=1e-6
        )


def test_retrievability_is_monotonic_in_elapsed_time():
    values = [retrievability(10.0, d) for d in range(0, 60, 5)]
    assert values == sorted(values, reverse=True)


def test_reviewing_late_is_not_penalised_more_than_reviewing_on_time():
    """A learner who returns after a long gap and still recalls the verse has
    demonstrated stronger memory — stability must not go backwards."""
    card = review(new_card(T0), GOOD, T0)
    on_time = review(card, GOOD, card.due_at)
    late = review(card, GOOD, card.due_at + timedelta(days=30))
    assert late.stability >= on_time.stability


def test_due_dates_are_timezone_aware_and_in_the_future():
    card = review(new_card(T0), GOOD, T0)
    assert card.due_at.tzinfo is not None
    assert card.due_at > T0
    assert card.last_reviewed_at == T0
