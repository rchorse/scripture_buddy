"""Pydantic schemas for LLM-generated exercise payloads.

These are the contract between the generation pipeline and the app: model
output that fails validation is dropped and logged, never inserted.
"""
from pydantic import BaseModel, Field, field_validator


class McqPayload(BaseModel):
    """Multiple-choice comprehension question about a chapter."""

    question: str = Field(min_length=10, max_length=300)
    choices: list[str] = Field(min_length=4, max_length=4)
    answer_index: int = Field(ge=0, le=3)
    verse_refs: list[str] = Field(min_length=1, max_length=5)
    explanation: str = Field(min_length=5, max_length=400)

    @field_validator("choices")
    @classmethod
    def choices_distinct(cls, v: list[str]) -> list[str]:
        if len({c.strip().lower() for c in v}) != len(v):
            raise ValueError("choices must be distinct")
        return v


class ClozePayload(BaseModel):
    """Fill-in-the-blank on a single verse; blank replaces a meaningful phrase."""

    verse_ref: str
    display_text: str = Field(description="Verse text with ____ where the answer goes")
    answer: str = Field(min_length=2, max_length=80)
    distractors: list[str] = Field(min_length=3, max_length=3)

    @field_validator("display_text")
    @classmethod
    def has_blank(cls, v: str) -> str:
        if "____" not in v:
            raise ValueError("display_text must contain ____")
        return v


class McqBatch(BaseModel):
    exercises: list[McqPayload] = Field(min_length=1, max_length=6)


class ClozeBatch(BaseModel):
    exercises: list[ClozePayload] = Field(min_length=1, max_length=6)


PAYLOAD_SCHEMAS = {"mcq": McqBatch, "cloze": ClozeBatch}
