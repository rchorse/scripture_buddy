"""Release cutting: snapshot all approved exercises for a work."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content import Exercise, Lesson, Release, ReleaseItem, Work


def cut_release(db: Session, work: Work, notes: str = "") -> Release:
    approved_ids = db.scalars(
        select(Exercise.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .where(Lesson.work_id == work.id, Exercise.state == "approved")
    ).all()

    next_version = (
        db.scalar(select(func.max(Release.version)).where(Release.work_id == work.id)) or 0
    ) + 1
    release = Release(work_id=work.id, version=next_version, notes=notes)
    db.add(release)
    db.flush()
    for ex_id in approved_ids:
        db.add(ReleaseItem(release_id=release.id, exercise_id=ex_id))
    db.commit()
    return release
