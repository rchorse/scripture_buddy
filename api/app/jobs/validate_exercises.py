"""Validate draft exercises against source scripture and auto-approve the clean ones.

Invoked as: {"task": "validate_exercises", "work_slug": "book-of-mormon"}

Idempotent: re-running re-validates anything still in ai_draft/in_review and
leaves owner decisions (approved/rejected/retired) alone.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.content import Exercise, Lesson, Work
from app.services.exercise_validation import validate_and_stage


def validate_exercises(work_slug: str) -> dict:
    stats = {"approved": 0, "needs_review": 0}
    with Session(get_engine()) as session:
        work = session.scalar(select(Work).where(Work.slug == work_slug))
        if work is None:
            raise ValueError(f"Unknown work: {work_slug}")

        rows = session.execute(
            select(Exercise, Lesson.division_id)
            .join(Lesson, Exercise.lesson_id == Lesson.id)
            .where(Lesson.work_id == work.id)
            .where(Exercise.state.in_(["ai_draft", "in_review"]))
        ).all()

        for exercise, division_id in rows:
            if validate_and_stage(session, exercise, division_id):
                stats["approved"] += 1
            else:
                stats["needs_review"] += 1
        session.commit()
    return {"status": "ok", **stats}
