"""Grade a submitted answer against an exercise payload.

Grading is deliberately server-side: the client never receives the correct
answer until after it submits, so answers can't be read out of the response
payload ahead of time.
"""
import hashlib
import random

from app.services.exercise_validation import normalize
from app.services.srs import AGAIN, GOOD


class GradingError(ValueError):
    pass


def grade(kind: str, payload: dict, answer) -> dict:
    """Return {correct, correct_answer, explanation}."""
    if kind == "mcq":
        choices = payload["choices"]
        index = payload["answer_index"]
        if isinstance(answer, str):
            submitted = next(
                (i for i, c in enumerate(choices) if normalize(c) == normalize(answer)),
                None,
            )
        elif isinstance(answer, int):
            submitted = answer
        else:
            raise GradingError("answer must be a choice index or text")
        return {
            "correct": submitted == index,
            "correct_answer": choices[index],
            "explanation": payload.get("explanation", ""),
        }

    if kind == "cloze":
        expected = payload["answer"]
        if not isinstance(answer, str):
            raise GradingError("answer must be text")
        return {
            "correct": normalize(answer) == normalize(expected),
            "correct_answer": expected,
            "explanation": f"{payload.get('verse_ref', '')}",
        }

    raise GradingError(f"cannot grade exercise kind: {kind}")


def rating_for(correct: bool) -> int:
    """Map a binary outcome to an SRS rating.

    Only GOOD/AGAIN are produced today; HARD and EASY are reserved for a
    future self-assessment control in the review UI.
    """
    return GOOD if correct else AGAIN


def _shuffled(options: list[str], seed: str) -> list[str]:
    """Deterministic per-(exercise, user) order.

    Deterministic so a refetch or reconnect doesn't reshuffle mid-question, and
    seeded per user so the correct answer isn't in the same position for
    everyone (for cloze it would otherwise always be first).
    """
    rng = random.Random(hashlib.sha256(seed.encode()).hexdigest())
    out = list(options)
    rng.shuffle(out)
    return out


def presentation_for(kind: str, payload: dict, seed: str) -> dict:
    """The client-safe view of an exercise — never contains the answer."""
    if kind == "mcq":
        return {
            "question": payload["question"],
            "options": _shuffled(payload["choices"], seed),
        }
    if kind == "cloze":
        options = [payload["answer"], *payload.get("distractors", [])]
        return {
            "verse_ref": payload.get("verse_ref", ""),
            "display_text": payload["display_text"],
            "options": _shuffled(options, seed),
        }
    return {}
