from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.principal import get_current_user
from app.models.content import Exercise, Lesson, Release, ReleaseItem
from app.models.core import User
from app.services import cards as card_service
from app.services.grading import GradingError, grade, presentation_for, rating_for

router = APIRouter(tags=["learning"])


def _is_released(db: Session, exercise: Exercise) -> bool:
    lesson = db.get(Lesson, exercise.lesson_id)
    if lesson is None or exercise.state == "retired":
        return False
    release_id = db.scalar(
        select(Release.id)
        .where(Release.work_id == lesson.work_id)
        .order_by(Release.version.desc())
        .limit(1)
    )
    if release_id is None:
        return False
    return db.scalar(
        select(ReleaseItem.exercise_id).where(
            ReleaseItem.release_id == release_id,
            ReleaseItem.exercise_id == exercise.id,
        )
    ) is not None


@router.post("/exercises/{exercise_id}/answer")
def answer_exercise(
    exercise_id: UUID,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Grade an answer and advance the learner's spaced-repetition card."""
    exercise = db.get(Exercise, exercise_id)
    if exercise is None or not _is_released(db, exercise):
        raise HTTPException(status_code=404, detail="Exercise not available")
    if "answer" not in body:
        raise HTTPException(status_code=400, detail="answer is required")

    try:
        result = grade(exercise.kind, exercise.payload, body["answer"])
    except GradingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    card = card_service.get_or_create(db, user.id, exercise.id)
    card_service.record_review(db, card, rating_for(result["correct"]))
    db.commit()

    return {
        **result,
        "due_at": card.due_at.isoformat(),
        "reps": card.reps,
        "lapses": card.lapses,
    }


@router.get("/reviews/due")
def due_reviews(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cards whose recall is predicted to be fading — the daily review queue."""
    out = []
    for card in card_service.due_cards(db, user.id, limit):
        exercise = db.get(Exercise, card.exercise_id)
        if exercise is None or not _is_released(db, exercise):
            continue
        lesson = db.get(Lesson, exercise.lesson_id)
        out.append(
            {
                "exercise_id": str(exercise.id),
                "kind": exercise.kind,
                "lesson_title": lesson.title if lesson else "",
                "due_at": card.due_at.isoformat(),
                **presentation_for(
                    exercise.kind, exercise.payload, f"{exercise.id}:{user.id}"
                ),
            }
        )
    return out
