"""Badge rules as data.

A badge's `rule` is a small JSON object evaluated against a snapshot of the
learner's stats, so adding a badge is an INSERT plus an art asset — no deploy.

Supported rules:
  {"type": "streak", "gte": 7}          longest streak reached
  {"type": "current_streak", "gte": 3}  streak right now
  {"type": "total_xp", "gte": 1000}
  {"type": "level", "gte": 5}
  {"type": "lessons_done", "gte": 10}
  {"type": "answers_correct", "gte": 100}
  {"type": "accuracy", "gte": 0.9, "min_answers": 50}
  {"type": "all", "rules": [...]}       every sub-rule must hold
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StatsSnapshot:
    total_xp: int = 0
    level: int = 1
    lessons_done: int = 0
    answers_correct: int = 0
    answers_total: int = 0
    current_streak: int = 0
    longest_streak: int = 0

    @property
    def accuracy(self) -> float:
        return self.answers_correct / self.answers_total if self.answers_total else 0.0


_FIELDS = {
    "streak": lambda s: s.longest_streak,
    "current_streak": lambda s: s.current_streak,
    "total_xp": lambda s: s.total_xp,
    "level": lambda s: s.level,
    "lessons_done": lambda s: s.lessons_done,
    "answers_correct": lambda s: s.answers_correct,
}


class BadgeRuleError(ValueError):
    pass


def evaluate(rule: dict, stats: StatsSnapshot) -> bool:
    """True when the learner qualifies. Unknown rule types are an error, not a
    silent False — a typo in a badge row should be loud."""
    kind = rule.get("type")

    if kind == "all":
        return all(evaluate(sub, stats) for sub in rule.get("rules", []))

    if kind == "accuracy":
        if stats.answers_total < rule.get("min_answers", 1):
            return False
        return stats.accuracy >= rule["gte"]

    getter = _FIELDS.get(kind)
    if getter is None:
        raise BadgeRuleError(f"unknown badge rule type: {kind!r}")
    if "gte" not in rule:
        raise BadgeRuleError(f"rule {kind!r} requires 'gte'")
    return getter(stats) >= rule["gte"]


# Seeded on first migration; more can be added as rows at any time.
STARTER_BADGES = [
    {
        "slug": "first-steps",
        "title": "First Steps",
        "description": "Answered your first question.",
        "art_key": "badge_first_steps",
        "rule": {"type": "answers_correct", "gte": 1},
        "sort_order": 10,
    },
    {
        "slug": "week-strong",
        "title": "Week Strong",
        "description": "Practised seven days in a row.",
        "art_key": "badge_week_strong",
        "rule": {"type": "streak", "gte": 7},
        "sort_order": 20,
    },
    {
        "slug": "month-faithful",
        "title": "Faithful Month",
        "description": "Practised thirty days in a row.",
        "art_key": "badge_month_faithful",
        "rule": {"type": "streak", "gte": 30},
        "sort_order": 30,
    },
    {
        "slug": "century",
        "title": "Century",
        "description": "Answered 100 questions correctly.",
        "art_key": "badge_century",
        "rule": {"type": "answers_correct", "gte": 100},
        "sort_order": 40,
    },
    {
        "slug": "sharp-eye",
        "title": "Sharp Eye",
        "description": "90% accuracy over 50 answers.",
        "art_key": "badge_sharp_eye",
        "rule": {"type": "accuracy", "gte": 0.9, "min_answers": 50},
        "sort_order": 50,
    },
    {
        "slug": "scholar",
        "title": "Scholar",
        "description": "Reached level 5.",
        "art_key": "badge_scholar",
        "rule": {"type": "level", "gte": 5},
        "sort_order": 60,
    },
    {
        "slug": "dedicated",
        "title": "Dedicated",
        "description": "Earned 1,000 XP.",
        "art_key": "badge_dedicated",
        "rule": {"type": "total_xp", "gte": 1000},
        "sort_order": 70,
    },
]
