"""content schema — scripture library, lessons/exercises, releases.

Scripture-agnostic: works → editions → divisions (self-referencing tree with a
flexible `kind`) → verses, so "1 Nephi > 3" and "Al-Baqarah" both fit without
schema changes.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

SCHEMA = "content"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class Work(Base):
    __tablename__ = "works"
    __table_args__ = (
        CheckConstraint("status IN ('draft','released')", name="status_valid"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(Text, unique=True)  # e.g. book-of-mormon
    title: Mapped[str] = mapped_column(Text)
    tradition: Mapped[str] = mapped_column(Text)  # lds | bible | quran | ...
    language: Mapped[str] = mapped_column(Text, default="en")
    license_note: Mapped[str] = mapped_column(Text, default="")  # provenance + license
    status: Mapped[str] = mapped_column(Text, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    editions: Mapped[list["Edition"]] = relationship(back_populates="work")


class Edition(Base):
    __tablename__ = "editions"
    __table_args__ = (
        UniqueConstraint("work_id", "slug", name="uq_editions_work_slug"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.works.id"))
    slug: Mapped[str] = mapped_column(Text)  # e.g. 1830, kjv
    title: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(default=False)

    work: Mapped[Work] = relationship(back_populates="editions")


class Division(Base):
    """Adjacency-list tree of books/chapters/surahs/sections within an edition."""

    __tablename__ = "divisions"
    __table_args__ = (
        UniqueConstraint("edition_id", "parent_id", "position", name="uq_divisions_pos"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    edition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.editions.id"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.divisions.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text)  # book | chapter | surah | section
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text)

    verses: Mapped[list["Verse"]] = relationship(back_populates="division")


class Verse(Base):
    __tablename__ = "verses"
    __table_args__ = (
        UniqueConstraint("division_id", "position", name="uq_verses_division_pos"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    division_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.divisions.id"))
    position: Mapped[int] = mapped_column(Integer)
    ref_label: Mapped[str] = mapped_column(Text)  # "1 Nephi 3:7"
    text_: Mapped[str] = mapped_column("text", Text)

    division: Mapped[Division] = relationship(back_populates="verses")


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('read','quiz','memorize','review_gate')", name="kind_valid"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.works.id"))
    division_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.divisions.id"))
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('mcq','cloze','word_bank','order_verse','match_ref')",
            name="kind_valid",
        ),
        CheckConstraint(
            "state IN ('ai_draft','in_review','approved','rejected','retired')",
            name="state_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.lessons.id"))
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    verse_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(Text, default="ai_draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.exercises.id"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(Text, default="llm")  # llm | owner
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint("work_id", "version", name="uq_releases_work_version"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.works.id"))
    version: Mapped[int] = mapped_column(Integer)
    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    notes: Mapped[str] = mapped_column(Text, default="")


class ReleaseItem(Base):
    __tablename__ = "release_items"
    __table_args__ = ({"schema": SCHEMA},)

    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.releases.id"), primary_key=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.exercises.id"), primary_key=True
    )


class BookRequest(Base):
    __tablename__ = "book_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','planned','declined','done')", name="status_valid"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # FK to core.users lands when the core models exist (M5); plain UUID until then.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    text_: Mapped[str] = mapped_column("text", Text)
    status: Mapped[str] = mapped_column(Text, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
