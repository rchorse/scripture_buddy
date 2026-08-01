"""Import generated exercises (JSONL in the data bucket) as ai_draft rows.

Invoked as: {"task": "import_exercises", "work_slug": "book-of-mormon",
             "s3_key": "generated/1-nephi-drafts.jsonl"}

Each line: {"custom_id": "<book-slug>--<chapter>--<kind>", "kind": ..., "payload": {...}}
Creates the target lesson per (chapter division, lesson kind) if missing:
mcq → quiz lesson, cloze → memorize lesson. Skips exact-duplicate payloads so
re-importing the same file is a no-op.
"""
import json
import os

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.content import Division, Edition, Exercise, Lesson, Work

LESSON_KIND_FOR_EXERCISE = {"mcq": "quiz", "cloze": "memorize"}
LESSON_TITLE_FOR_KIND = {"quiz": "Chapter quiz", "memorize": "Memorize"}


def import_exercises(work_slug: str, s3_key: str) -> dict:
    bucket = os.environ["DATA_BUCKET"]
    body = boto3.client("s3").get_object(Bucket=bucket, Key=s3_key)["Body"].read()
    lines = [json.loads(line) for line in body.decode().splitlines() if line.strip()]

    stats = {"inserted": 0, "duplicates": 0, "unmatched_chapter": 0}
    with Session(get_engine()) as session:
        work = session.scalar(select(Work).where(Work.slug == work_slug))
        if work is None:
            raise ValueError(f"Unknown work: {work_slug}")
        edition = session.scalar(
            select(Edition).where(Edition.work_id == work.id, Edition.is_default)
        )

        lesson_cache: dict = {}
        for line in lines:
            book_slug, chapter_pos, _kind = line["custom_id"].split("--")
            book = session.scalar(
                select(Division).where(
                    Division.edition_id == edition.id,
                    Division.parent_id.is_(None),
                    Division.slug == book_slug,
                )
            )
            chapter = (
                session.scalar(
                    select(Division).where(
                        Division.parent_id == book.id,
                        Division.position == int(chapter_pos),
                    )
                )
                if book
                else None
            )
            if chapter is None:
                stats["unmatched_chapter"] += 1
                continue

            lesson_kind = LESSON_KIND_FOR_EXERCISE[line["kind"]]
            cache_key = (str(chapter.id), lesson_kind)
            lesson = lesson_cache.get(cache_key)
            if lesson is None:
                lesson = session.scalar(
                    select(Lesson).where(
                        Lesson.division_id == chapter.id, Lesson.kind == lesson_kind
                    )
                )
                if lesson is None:
                    lesson = Lesson(
                        work_id=work.id,
                        division_id=chapter.id,
                        position=(book.position * 1000) + chapter.position,
                        kind=lesson_kind,
                        title=f"{chapter.title} — {LESSON_TITLE_FOR_KIND[lesson_kind]}",
                    )
                    session.add(lesson)
                    session.flush()
                lesson_cache[cache_key] = lesson

            duplicate = session.scalar(
                select(Exercise.id).where(
                    Exercise.lesson_id == lesson.id,
                    Exercise.kind == line["kind"],
                    Exercise.payload == line["payload"],
                )
            )
            if duplicate:
                stats["duplicates"] += 1
                continue
            session.add(
                Exercise(
                    lesson_id=lesson.id,
                    kind=line["kind"],
                    payload=line["payload"],
                    verse_ids=[],
                    difficulty=1,
                    state="ai_draft",
                    created_by="llm",
                )
            )
            stats["inserted"] += 1
        session.commit()
    return {"status": "ok", **stats}
