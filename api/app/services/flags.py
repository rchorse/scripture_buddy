"""Learner flags on exercises.

Flags are a signal for the owner, never an automatic action: a flagged
exercise keeps being served until the owner reviews it in /admin/flags and
decides to retire it or dismiss the flags. One flag per user per exercise.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content import ExerciseFlag

VALID_REASONS = ("wrong_answer", "confusing", "not_in_text", "typo", "other")


def flag_exercise(
    db: Session, exercise_id, user_id, reason: str, note: str = ""
) -> dict:
    if reason not in VALID_REASONS:
        raise ValueError(f"invalid reason: {reason}")
    existing = db.scalar(
        select(ExerciseFlag).where(
            ExerciseFlag.exercise_id == exercise_id, ExerciseFlag.user_id == user_id
        )
    )
    if existing is None:
        db.add(
            ExerciseFlag(
                exercise_id=exercise_id,
                user_id=user_id,
                reason=reason,
                note=note[:1000],
            )
        )
    elif existing.resolved_at is not None:
        # The owner dismissed this user's earlier flag. If they're reporting it
        # again, reopen the same row — one row per user per exercise, but a
        # dismissal must never permanently silence that user on this item.
        existing.resolved_at = None
        existing.reason = reason
        existing.note = note[:1000]
    db.commit()

    unresolved = db.scalar(
        select(func.count())
        .select_from(ExerciseFlag)
        .where(
            ExerciseFlag.exercise_id == exercise_id,
            ExerciseFlag.resolved_at.is_(None),
        )
    )
    return {"status": "ok", "flags": unresolved}
