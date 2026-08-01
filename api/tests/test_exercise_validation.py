"""Validation is the release gate now that exercises auto-approve, so its
failure cases matter more than its happy path."""
from app.services.exercise_validation import normalize, validate_exercise

VERSE = (
    "And it came to pass that I, Nephi, said unto my father: I will go and do "
    "the things which the Lord hath commanded, for I know that the Lord giveth "
    "no commandments unto the children of men, save he shall prepare a way for them."
)


class FakeDB:
    """Stands in for a Session; validation only reads verses for a chapter."""

    def __init__(self, verses):
        self._verses = verses

    def scalars(self, _stmt):
        return self

    def all(self):
        return self._verses


class FakeVerse:
    def __init__(self, ref_label, text):
        self.ref_label = ref_label
        self.text_ = text


def make_db():
    return FakeDB([FakeVerse("1 Nephi 3:7", VERSE)])


def test_normalize_ignores_case_and_punctuation():
    assert normalize("I, Nephi—said:") == "i nephi said"


def test_good_cloze_passes():
    payload = {
        "verse_ref": "1 Nephi 3:7",
        "display_text": "And it came to pass that I, Nephi, said unto my father: ____,",
        "answer": "I will go and do the things which the Lord hath commanded",
        "distractors": ["I will flee into the desert", "I will build a ship", "I will pray"],
    }
    assert validate_exercise(make_db(), "cloze", payload, "div") == []


def test_fabricated_cloze_answer_is_rejected():
    payload = {
        "verse_ref": "1 Nephi 3:7",
        "display_text": "And it came to pass that I, Nephi, said unto my father: ____,",
        "answer": "I shall depart unto the land of promise",  # not in the verse
        "distractors": ["a", "b", "c"],
    }
    problems = validate_exercise(make_db(), "cloze", payload, "div")
    assert any("does not appear" in p for p in problems)


def test_distractor_taken_from_the_text_is_rejected():
    payload = {
        "verse_ref": "1 Nephi 3:7",
        "display_text": "And it came to pass that I, Nephi, said unto my father: ____,",
        "answer": "I will go and do the things which the Lord hath commanded",
        # This phrase IS in the verse, so it is not plausibly wrong.
        "distractors": ["prepare a way for them", "b", "c"],
    }
    problems = validate_exercise(make_db(), "cloze", payload, "div")
    assert any("appears in the chapter text" in p for p in problems)


def test_unknown_verse_ref_is_rejected():
    payload = {
        "verse_ref": "1 Nephi 99:1",
        "display_text": "____",
        "answer": "I will go and do",
        "distractors": ["a", "b", "c"],
    }
    problems = validate_exercise(make_db(), "cloze", payload, "div")
    assert any("not in this chapter" in p for p in problems)


def test_mcq_with_bad_citation_is_rejected():
    payload = {
        "question": "What did Nephi say?",
        "choices": ["a", "b", "c", "d"],
        "answer_index": 0,
        "verse_refs": ["1 Nephi 3:7", "1 Nephi 42:1"],
        "explanation": "...",
    }
    problems = validate_exercise(make_db(), "mcq", payload, "div")
    assert any("1 Nephi 42:1" in p for p in problems)


def test_mcq_with_duplicate_choices_is_rejected():
    payload = {
        "question": "What did Nephi say?",
        "choices": ["Yes", "yes.", "c", "d"],  # same after normalization
        "answer_index": 0,
        "verse_refs": ["1 Nephi 3:7"],
        "explanation": "...",
    }
    problems = validate_exercise(make_db(), "mcq", payload, "div")
    assert any("distinct" in p for p in problems)
