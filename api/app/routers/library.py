from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.principal import get_current_user
from app.models.content import Division, Edition, Verse, Work
from app.models.core import ReadingPosition, User

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/works")
def list_works(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Released works only — drafts are visible to clients never (owner uses /admin)."""
    works = db.scalars(select(Work).where(Work.status == "released")).all()
    return [
        {"id": str(w.id), "slug": w.slug, "title": w.title, "tradition": w.tradition}
        for w in works
    ]


def _work_or_404(db: Session, slug: str) -> Work:
    work = db.scalar(select(Work).where(Work.slug == slug))
    if work is None or work.status != "released":
        raise HTTPException(status_code=404, detail="Work not found")
    return work


@router.get("/works/{slug}/toc")
def table_of_contents(
    slug: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Books with their chapter divisions (id, position, title) for the default edition."""
    work = _work_or_404(db, slug)
    edition = db.scalar(
        select(Edition)
        .where(Edition.work_id == work.id, Edition.is_default)
        .order_by(Edition.slug)
    )
    if edition is None:
        raise HTTPException(status_code=404, detail="Work has no default edition")
    books = db.scalars(
        select(Division)
        .where(Division.edition_id == edition.id, Division.parent_id.is_(None))
        .order_by(Division.position)
    ).all()
    # Single query for all chapters, grouped in Python (toc is small: ~250 rows).
    chapters = db.scalars(
        select(Division)
        .where(Division.parent_id.in_([b.id for b in books]))
        .order_by(Division.position)
    ).all()
    by_parent: dict = {}
    for ch in chapters:
        by_parent.setdefault(ch.parent_id, []).append(
            {"id": str(ch.id), "position": ch.position, "title": ch.title}
        )
    return {
        "work": {"id": str(work.id), "slug": work.slug, "title": work.title},
        "books": [
            {
                "id": str(b.id),
                "position": b.position,
                "title": b.title,
                "slug": b.slug,
                "chapters": by_parent.get(b.id, []),
            }
            for b in books
        ],
    }


@router.get("/divisions/{division_id}/verses")
def get_verses(
    division_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    verses = db.scalars(
        select(Verse).where(Verse.division_id == division_id).order_by(Verse.position)
    ).all()
    if not verses:
        raise HTTPException(status_code=404, detail="No verses in division")
    return [
        {"position": v.position, "ref": v.ref_label, "text": v.text_} for v in verses
    ]


@router.get("/works/{slug}/position")
def get_position(
    slug: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    work = _work_or_404(db, slug)
    pos = db.get(ReadingPosition, (user.id, work.id))
    if pos is None:
        return {"division_id": None, "verse_position": 1}
    return {"division_id": str(pos.division_id), "verse_position": pos.verse_position}


@router.put("/works/{slug}/position")
def put_position(
    slug: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    work = _work_or_404(db, slug)
    division_id = UUID(body["division_id"])
    verse_position = int(body.get("verse_position", 1))
    if db.get(Division, division_id) is None:
        raise HTTPException(status_code=400, detail="Unknown division")
    pos = db.get(ReadingPosition, (user.id, work.id))
    if pos is None:
        pos = ReadingPosition(
            user_id=user.id,
            work_id=work.id,
            division_id=division_id,
            verse_position=verse_position,
        )
        db.add(pos)
    else:
        pos.division_id = division_id
        pos.verse_position = verse_position
    db.commit()
    return {"status": "ok"}
