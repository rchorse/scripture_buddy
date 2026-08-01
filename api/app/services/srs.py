"""FSRS-lite spaced-repetition scheduler.

A simplified Free Spaced Repetition Scheduler: memory is modelled by
*stability* (days until recall probability falls to RETENTION_TARGET) and
*difficulty* (intrinsic hardness, 1–10). After each review both are updated and
the next interval is chosen so the card comes back just as recall starts to
fade.

Pure functions with an injected `now` so behaviour is testable at fixed clocks.
Ratings follow the SRS convention: 1 again, 2 hard, 3 good, 4 easy.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4

# Target recall probability when a card comes due.
RETENTION_TARGET = 0.9
# Decay constant from the FSRS power-law forgetting curve.
_DECAY = -0.5
_FACTOR = 19 / 81

# Initial stability in days, by first-review rating.
INITIAL_STABILITY = {AGAIN: 0.4, HARD: 1.2, GOOD: 3.0, EASY: 8.0}
INITIAL_DIFFICULTY = {AGAIN: 7.5, HARD: 6.0, GOOD: 5.0, EASY: 3.5}

MIN_STABILITY = 0.1
MAX_STABILITY = 3650.0
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0
# A lapse should sting but not erase everything the learner built.
LAPSE_STABILITY_FACTOR = 0.35


@dataclass(frozen=True)
class CardState:
    state: str
    stability: float
    difficulty: float
    reps: int
    lapses: int
    due_at: datetime
    last_reviewed_at: datetime | None = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def retrievability(stability: float, elapsed_days: float) -> float:
    """Probability of recall after `elapsed_days` given `stability`."""
    if stability <= 0:
        return 0.0
    if elapsed_days <= 0:
        return 1.0
    return (1 + _FACTOR * elapsed_days / stability) ** _DECAY


def interval_for_stability(stability: float) -> float:
    """Days until retrievability decays to RETENTION_TARGET."""
    return (stability / _FACTOR) * (RETENTION_TARGET ** (1 / _DECAY) - 1)


def _next_difficulty(difficulty: float, rating: int) -> float:
    # Drift toward easier on success, harder on failure; GOOD is neutral.
    delta = {AGAIN: 1.6, HARD: 0.6, GOOD: 0.0, EASY: -0.8}[rating]
    return _clamp(difficulty + delta, MIN_DIFFICULTY, MAX_DIFFICULTY)


def _next_stability(
    stability: float, difficulty: float, rating: int, elapsed_days: float
) -> float:
    if rating == AGAIN:
        # Lapse: keep a fraction, scaled down further for difficult material.
        return _clamp(
            stability * LAPSE_STABILITY_FACTOR * (1.1 - difficulty / 20),
            MIN_STABILITY,
            MAX_STABILITY,
        )

    recall = retrievability(stability, elapsed_days)
    # Reviewing a card you had nearly forgotten teaches more than one you just
    # saw — this is the FSRS spacing effect, strongest at low retrievability.
    spacing_bonus = 1 + (1 - recall) * 1.5
    # Tuned so an on-time GOOD review at average difficulty roughly doubles the
    # interval (3d → 6d → 14d → 30d …), matching published FSRS behaviour.
    ease = {HARD: 1.15, GOOD: 2.3, EASY: 3.4}[rating]
    difficulty_penalty = 1 - (difficulty - 1) / 18
    growth = 1 + (ease - 1) * spacing_bonus * difficulty_penalty
    return _clamp(stability * growth, MIN_STABILITY, MAX_STABILITY)


def new_card(now: datetime) -> CardState:
    return CardState(
        state="new", stability=0.0, difficulty=5.0, reps=0, lapses=0, due_at=now
    )


def review(card: CardState, rating: int, now: datetime) -> CardState:
    """Apply a review and return the updated card state."""
    if rating not in (AGAIN, HARD, GOOD, EASY):
        raise ValueError(f"rating must be 1-4, got {rating}")

    first_review = card.reps == 0 or card.stability <= 0
    if first_review:
        stability = INITIAL_STABILITY[rating]
        difficulty = INITIAL_DIFFICULTY[rating]
        elapsed = 0.0
    else:
        elapsed = max(
            0.0,
            (now - card.last_reviewed_at).total_seconds() / 86400
            if card.last_reviewed_at
            else 0.0,
        )
        difficulty = _next_difficulty(card.difficulty, rating)
        stability = _next_stability(card.stability, difficulty, rating, elapsed)

    if rating == AGAIN:
        state = "lapsed"
        lapses = card.lapses + (0 if first_review else 1)
        # Failed cards come back within the same session-ish window.
        interval_days = min(interval_for_stability(stability), 0.5)
    else:
        state = "review" if card.reps >= 1 or rating >= GOOD else "learning"
        lapses = card.lapses
        interval_days = max(interval_for_stability(stability), 0.02)

    return CardState(
        state=state,
        stability=stability,
        difficulty=difficulty,
        reps=card.reps + 1,
        lapses=lapses,
        due_at=now + timedelta(days=interval_days),
        last_reviewed_at=now,
    )
