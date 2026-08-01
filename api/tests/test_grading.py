import pytest

from app.services.grading import (
    GradingError,
    grade,
    presentation_for,
    rating_for,
)
from app.services.srs import AGAIN, GOOD

MCQ = {
    "question": "What did Nephi say?",
    "choices": ["I will go and do", "I will flee", "I will wait", "I will ask again"],
    "answer_index": 0,
    "verse_refs": ["1 Nephi 3:7"],
    "explanation": "Verse 7.",
}

CLOZE = {
    "verse_ref": "1 Nephi 3:7",
    "display_text": "I, Nephi, said unto my father: ____",
    "answer": "I will go and do the things which the Lord hath commanded",
    "distractors": ["I will depart", "I will build a ship", "I will pray"],
}


def test_mcq_correct_by_index_and_by_text():
    assert grade("mcq", MCQ, 0)["correct"]
    assert grade("mcq", MCQ, "I will go and do")["correct"]
    assert not grade("mcq", MCQ, 2)["correct"]


def test_mcq_text_match_ignores_case_and_punctuation():
    assert grade("mcq", MCQ, "i will go and do!")["correct"]


def test_cloze_match_is_forgiving_of_punctuation():
    assert grade(
        "cloze", CLOZE, "I will go and do the things which the Lord hath commanded,"
    )["correct"]
    assert not grade("cloze", CLOZE, "I will depart")["correct"]


def test_grade_returns_the_answer_only_after_submission():
    result = grade("mcq", MCQ, 1)
    assert result["correct_answer"] == "I will go and do"
    assert result["explanation"] == "Verse 7."


def test_unknown_kind_and_bad_answer_types_are_rejected():
    with pytest.raises(GradingError):
        grade("order_verse", {}, "x")
    with pytest.raises(GradingError):
        grade("cloze", CLOZE, 3)


def test_rating_mapping():
    assert rating_for(True) == GOOD
    assert rating_for(False) == AGAIN


def test_presentation_never_contains_the_answer():
    for kind, payload in (("mcq", MCQ), ("cloze", CLOZE)):
        view = presentation_for(kind, payload, seed="ex:user")
        assert "answer" not in view
        assert "answer_index" not in view
        assert "distractors" not in view
        assert len(view["options"]) == 4


def test_presentation_order_is_stable_per_user_but_varies_across_users():
    a1 = presentation_for("cloze", CLOZE, "ex1:userA")["options"]
    a2 = presentation_for("cloze", CLOZE, "ex1:userA")["options"]
    assert a1 == a2, "same user must see a stable order across refetches"

    seeds = [f"ex1:user{i}" for i in range(30)]
    positions = {
        presentation_for("cloze", CLOZE, s)["options"].index(CLOZE["answer"])
        for s in seeds
    }
    assert len(positions) > 1, "answer must not sit at a fixed position for everyone"


def test_presentation_options_contain_every_choice():
    view = presentation_for("cloze", CLOZE, "ex:user")
    assert sorted(view["options"]) == sorted([CLOZE["answer"], *CLOZE["distractors"]])
