from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.principal import get_current_user
from app.models.content import Exercise, Lesson, Release, ReleaseItem
from app.models.core import User
from app.services.flags import flag_exercise
from app.services.grading import presentation_for

router = APIRouter(prefix="/lessons", tags=["lessons"])


def _latest_release_id(db: Session, work_id):
    return db.scalar(
        select(Release.id)
        .where(Release.work_id == work_id)
        .order_by(Release.version.desc())
        .limit(1)
    )


@router.get("/by-division/{division_id}")
def lessons_for_division(
    division_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lessons for a chapter with released exercise counts. Clients NEVER see
    unreleased exercises — everything is joined through the latest release."""
    lessons = db.scalars(
        select(Lesson).where(Lesson.division_id == division_id).order_by(Lesson.kind)
    ).all()
    out = []
    for lesson in lessons:
        release_id = _latest_release_id(db, lesson.work_id)
        count = 0
        if release_id:
            count = db.scalar(
                select(func.count())
                .select_from(Exercise)
                .join(ReleaseItem, ReleaseItem.exercise_id == Exercise.id)
                .where(
                    ReleaseItem.release_id == release_id,
                    Exercise.lesson_id == lesson.id,
                    # Retired items stay in the release snapshot but must stop
                    # being served the moment they're pulled.
                    Exercise.state != "retired",
                )
            )
        if count:
            out.append(
                {
                    "id": str(lesson.id),
                    "kind": lesson.kind,
                    "title": lesson.title,
                    "exercise_count": count,
                }
            )
    return out


@router.get("/{lesson_id}/exercises")
def exercises_for_lesson(
    lesson_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        return []
    release_id = _latest_release_id(db, lesson.work_id)
    if release_id is None:
        return []
    exercises = db.scalars(
        select(Exercise)
        .join(ReleaseItem, ReleaseItem.exercise_id == Exercise.id)
        .where(
            ReleaseItem.release_id == release_id,
            Exercise.lesson_id == lesson_id,
            Exercise.state != "retired",
        )
    ).all()
    # Never ship the answer to the client — only the presentation view.
    return [
        {
            "id": str(e.id),
            "kind": e.kind,
            "difficulty": e.difficulty,
            **presentation_for(e.kind, e.payload, f"{e.id}:{user.id}"),
        }
        for e in exercises
    ]


@router.post("/exercises/{exercise_id}/flag")
def flag(
    exercise_id: UUID,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Learner reports a bad exercise. Enough reports retire it automatically."""
    if db.get(Exercise, exercise_id) is None:
        raise HTTPException(status_code=404, detail="Unknown exercise")
    try:
        return flag_exercise(
            db,
            exercise_id,
            user.id,
            reason=body.get("reason", "other"),
            note=body.get("note", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
