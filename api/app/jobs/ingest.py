"""Ingest a scripture work from bcbooks/scriptures-json shaped JSON.

Invoked as: {"task": "ingest", "work_slug": "book-of-mormon", "s3_key": "sources/book-of-mormon.json"}

Idempotent: works/editions keyed on slug, divisions on (parent, position),
verses on (division, position). Re-running updates text in place and never
duplicates rows.
"""
import json
import os

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.content import Division, Edition, Verse, Work


def _slugify(title: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-").replace("--", "-")


def ingest_scriptures(work_slug: str, s3_key: str) -> dict:
    bucket = os.environ["DATA_BUCKET"]
    obj = boto3.client("s3").get_object(Bucket=bucket, Key=s3_key)
    data = json.loads(obj["Body"].read())

    counts = {"books": 0, "chapters": 0, "verses": 0}
    with Session(get_engine()) as session:
        work = session.scalar(select(Work).where(Work.slug == work_slug))
        if work is None:
            work = Work(
                slug=work_slug,
                title=data.get("title", work_slug),
                tradition="lds",
                language="en",
                status="draft",
            )
            session.add(work)
            session.flush()
        work.license_note = (
            f"bcbooks/scriptures-json version {data.get('version')}, "
            f"last_modified {data.get('last_modified')}; public domain"
        )

        edition_slug = str(data.get("version", "1"))
        edition = session.scalar(
            select(Edition).where(Edition.work_id == work.id, Edition.slug == edition_slug)
        )
        if edition is None:
            edition = Edition(
                work_id=work.id,
                slug=edition_slug,
                title=data.get("title", work_slug),
                source_url="https://github.com/bcbooks/scriptures-json",
                is_default=True,
            )
            session.add(edition)
            session.flush()

        existing_books = {
            d.slug: d
            for d in session.scalars(
                select(Division).where(
                    Division.edition_id == edition.id, Division.parent_id.is_(None)
                )
            )
        }

        for book_pos, book in enumerate(data["books"], start=1):
            book_slug = book.get("lds_slug") or _slugify(book["book"])
            book_div = existing_books.get(book_slug)
            if book_div is None:
                book_div = Division(
                    edition_id=edition.id,
                    parent_id=None,
                    kind="book",
                    position=book_pos,
                    title=book["book"],
                    slug=book_slug,
                )
                session.add(book_div)
                session.flush()
            counts["books"] += 1

            existing_chapters = {
                d.position: d
                for d in session.scalars(
                    select(Division).where(Division.parent_id == book_div.id)
                )
            }
            for chapter in book["chapters"]:
                ch_pos = chapter["chapter"]
                ch_div = existing_chapters.get(ch_pos)
                if ch_div is None:
                    ch_div = Division(
                        edition_id=edition.id,
                        parent_id=book_div.id,
                        kind="chapter",
                        position=ch_pos,
                        title=chapter.get("reference", f"{book['book']} {ch_pos}"),
                        slug=str(ch_pos),
                    )
                    session.add(ch_div)
                    session.flush()
                counts["chapters"] += 1

                existing_verses = {
                    v.position: v
                    for v in session.scalars(
                        select(Verse).where(Verse.division_id == ch_div.id)
                    )
                }
                for verse in chapter["verses"]:
                    v_pos = verse["verse"]
                    row = existing_verses.get(v_pos)
                    if row is None:
                        session.add(
                            Verse(
                                division_id=ch_div.id,
                                position=v_pos,
                                ref_label=verse["reference"],
                                text_=verse["text"],
                            )
                        )
                    else:
                        row.ref_label = verse["reference"]
                        row.text_ = verse["text"]
                    counts["verses"] += 1

        session.commit()

    return {"status": "ok", "work": work_slug, "counts": counts}
