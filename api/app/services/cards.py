"""Persistence for SRS cards — bridges the pure scheduler to the database."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.srs import Card, ReviewLog
from app.services import srs


def _to_state(card: Card) -> srs.CardState:
    return srs.CardState(
        state=card.state,
        stability=card.stability,
        difficulty=card.difficulty,
        reps=card.reps,
        lapses=card.lapses,
        due_at=card.due_at,
        last_reviewed_at=card.last_reviewed_at,
    )


def get_or_create(db: Session, user_id, exercise_id) -> Card:
    card = db.scalar(
        select(Card).where(Card.user_id == user_id, Card.exercise_id == exercise_id)
    )
    if card is None:
        now = datetime.now(UTC)
        card = Card(user_id=user_id, exercise_id=exercise_id, due_at=now)
        db.add(card)
        db.flush()
    return card


def record_review(db: Session, card: Card, rating: int, now: datetime | None = None) -> Card:
    """Apply a rating to a card, append the log, and persist. Caller commits."""
    now = now or datetime.now(UTC)
    before = _to_state(card)
    elapsed = (
        (now - card.last_reviewed_at).total_seconds() / 86400
        if card.last_reviewed_at
        else 0.0
    )
    scheduled = (
        (card.due_at - card.last_reviewed_at).total_seconds() / 86400
        if card.last_reviewed_at
        else 0.0
    )
    after = srs.review(before, rating, now)

    card.state = after.state
    card.stability = after.stability
    card.difficulty = after.difficulty
    card.reps = after.reps
    card.lapses = after.lapses
    card.due_at = after.due_at
    card.last_reviewed_at = after.last_reviewed_at

    db.add(
        ReviewLog(
            card_id=card.id,
            rating=rating,
            elapsed_days=elapsed,
            scheduled_days=scheduled,
            stability_after=after.stability,
            difficulty_after=after.difficulty,
            reviewed_at=now,
        )
    )
    return card


def due_cards(db: Session, user_id, limit: int = 20) -> list[Card]:
    return list(
        db.scalars(
            select(Card)
            .where(Card.user_id == user_id, Card.due_at <= datetime.now(UTC))
            .order_by(Card.due_at)
            .limit(limit)
        )
    )
