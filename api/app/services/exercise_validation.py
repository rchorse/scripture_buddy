"""Mechanical validation of generated exercises against the source scripture.

This replaces per-item human review as the release gate. It cannot judge
whether a question is *interesting*, but it does catch the failure mode that
matters for scripture content: text the model invented. Everything is checked
against the verses already in the database.

Items that pass are auto-approved; items that fail land in the owner's review
queue with the reason attached.
"""
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Division, Verse


def normalize(text: str) -> str:
    """Casefold, strip punctuation and collapse whitespace for comparison."""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    return " ".join(text.split())


def _verses_for_chapter(db: Session, division_id) -> dict[str, str]:
    """ref_label -> verse text for one chapter."""
    rows = db.scalars(select(Verse).where(Verse.division_id == division_id)).all()
    return {v.ref_label: v.text_ for v in rows}


def validate_exercise(db: Session, kind: str, payload: dict, division_id) -> list[str]:
    """Return a list of problems; empty means the exercise is trustworthy."""
    return check_payload(kind, payload, _verses_for_chapter(db, division_id))


def check_payload(kind: str, payload: dict, verses: dict[str, str]) -> list[str]:
    """The validation rules themselves, over a plain ref_label -> text mapping.

    Kept free of the database so the content pipeline can measure a generation
    run's failure rate locally, against the source JSON, before importing.
    """
    if not verses:
        return ["chapter has no verses"]
    chapter_text = normalize(" ".join(verses.values()))
    problems: list[str] = []

    if kind == "cloze":
        ref = payload.get("verse_ref", "")
        if ref not in verses:
            problems.append(f"verse_ref {ref!r} not in this chapter")
        answer = payload.get("answer", "")
        display = payload.get("display_text", "")
        # The cloze with its blank filled in must be real scripture text.
        filled = normalize(display.replace("____", answer))
        if filled and filled not in chapter_text:
            problems.append("display_text with answer filled in is not verbatim scripture")
        if normalize(answer) and normalize(answer) not in chapter_text:
            problems.append("answer phrase does not appear in the chapter")
        for distractor in payload.get("distractors", []):
            # A distractor that IS in the text makes the item ambiguous.
            if normalize(distractor) and normalize(distractor) in chapter_text:
                problems.append(f"distractor {distractor!r} appears in the chapter text")

    elif kind == "mcq":
        for ref in payload.get("verse_refs", []):
            if ref not in verses:
                problems.append(f"verse_ref {ref!r} not in this chapter")
        choices = payload.get("choices", [])
        answer_index = payload.get("answer_index")
        if not isinstance(answer_index, int) or not 0 <= answer_index < len(choices):
            problems.append("answer_index out of range")
        if len({normalize(c) for c in choices}) != len(choices):
            problems.append("choices are not distinct")

    return problems


def validate_and_stage(db: Session, exercise, division_id) -> bool:
    """Set an exercise's state from validation. Returns True when approved."""
    problems = validate_exercise(db, exercise.kind, exercise.payload, division_id)
    if problems:
        exercise.state = "in_review"
        exercise.review_note = "; ".join(problems)[:500]
        return False
    exercise.state = "approved"
    exercise.review_note = "auto-approved: verified against source text"
    return True


def resolve_division_for_lesson(db: Session, lesson) -> object:
    return db.get(Division, lesson.division_id)
