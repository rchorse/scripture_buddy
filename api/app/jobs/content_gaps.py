"""Report lessons that fell below the target exercise count.

Rejecting or retiring an exercise leaves a hole — nothing refills it
automatically. This job finds those holes so the generation pipeline can
regenerate just the affected chapters, and hands back the rejected payloads so
the prompt can be told what not to repeat.

Invoked as: {"task": "content_gaps", "work_slug": "book-of-mormon", "target": 4}
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.content import Division, Edition, Exercise, Lesson, Work

# Exercise kind produced by each lesson kind — mirrors import_exercises.
EXERCISE_KIND_FOR_LESSON = {"quiz": "mcq", "memorize": "cloze"}
DEFAULT_TARGET = 4


def content_gaps(work_slug: str, target: int = DEFAULT_TARGET) -> dict:
    with Session(get_engine()) as session:
        work = session.scalar(select(Work).where(Work.slug == work_slug))
        if work is None:
            raise ValueError(f"Unknown work: {work_slug}")
        edition = session.scalar(
            select(Edition).where(Edition.work_id == work.id, Edition.is_default)
        )

        # Usable = anything that could still reach a release.
        usable = (
            select(Exercise.lesson_id, func.count().label("n"))
            .where(Exercise.state.in_(["approved", "ai_draft", "in_review"]))
            .group_by(Exercise.lesson_id)
            .subquery()
        )
        rows = session.execute(
            select(Lesson, func.coalesce(usable.c.n, 0))
            .join(usable, usable.c.lesson_id == Lesson.id, isouter=True)
            .where(Lesson.work_id == work.id)
            .order_by(Lesson.position)
        ).all()

        gaps = []
        for lesson, count in rows:
            if count >= target:
                continue
            chapter = session.get(Division, lesson.division_id)
            book = session.get(Division, chapter.parent_id) if chapter else None
            if chapter is None or book is None:
                continue
            rejected = session.scalars(
                select(Exercise).where(
                    Exercise.lesson_id == lesson.id,
                    Exercise.state.in_(["rejected", "retired"]),
                )
            ).all()
            gaps.append(
                {
                    "lesson_id": str(lesson.id),
                    "lesson_title": lesson.title,
                    "lesson_kind": lesson.kind,
                    "exercise_kind": EXERCISE_KIND_FOR_LESSON.get(lesson.kind),
                    "book_slug": book.slug,
                    "book_title": book.title,
                    "chapter": chapter.position,
                    "have": count,
                    "need": target - count,
                    "avoid": [
                        {"payload": e.payload, "why": e.review_note} for e in rejected
                    ],
                }
            )

        # Chapters that have no lesson at all for a kind are gaps too: every
        # generated item for that chapter was rejected, so the lesson row
        # exists but empty — or generation never covered it.
        return {
            "status": "ok",
            "work": work_slug,
            "edition": edition.slug if edition else None,
            "target": target,
            "gap_count": len(gaps),
            "missing_total": sum(g["need"] for g in gaps),
            "gaps": gaps,
        }
