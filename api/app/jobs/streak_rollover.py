"""Hourly streak rollover, in each learner's own timezone.

Runs every hour and processes only the learners whose local midnight has just
passed — that's why the job is hourly rather than daily: local midnight happens
at a different UTC hour in every timezone.

Idempotent: `last_rollover_local_date` guards against double-processing when
the schedule fires twice or a retry occurs.
"""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.core import User
from app.models.game import Streak
from app.services import streaks
from app.services.gamification import _apply_state, _to_state


def streak_rollover(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    counts = {"checked": 0, "kept": 0, "frozen": 0, "reset": 0, "noop": 0}

    with Session(get_engine()) as session:
        rows = session.execute(
            select(Streak, User.timezone)
            .join(User, User.id == Streak.user_id)
            .where(Streak.current > 0)
        ).all()

        for streak_row, timezone_name in rows:
            today = streaks.local_date(now, timezone_name)
            if streak_row.last_rollover_local_date == today:
                continue  # already handled this local day
            counts["checked"] += 1
            state, outcome = streaks.roll_over(_to_state(streak_row), today)
            _apply_state(streak_row, state)
            counts[outcome] = counts.get(outcome, 0) + 1
        session.commit()

    return {"status": "ok", **counts}
