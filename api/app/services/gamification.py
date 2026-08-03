"""Awarding XP, and everything that cascades from it.

One entry point — `award_xp` — appends to the ledger, updates the projection,
touches the streak in the learner's local timezone, and evaluates badges. It
returns a rewards payload the client renders as the post-lesson celebration.
"""
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import User
from app.models.game import Badge, Streak, UserBadge, UserStats, XpEvent
from app.services import leveling, streaks
from app.services.badges import BadgeRuleError, StatsSnapshot, evaluate


@dataclass
class Rewards:
    xp_awarded: int = 0
    total_xp: int = 0
    level: int = 1
    leveled_up: bool = False
    streak: int = 0
    streak_extended: bool = False
    new_badges: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "xp_awarded": self.xp_awarded,
            "total_xp": self.total_xp,
            "level": self.level,
            "leveled_up": self.leveled_up,
            "streak": self.streak,
            "streak_extended": self.streak_extended,
            "new_badges": self.new_badges,
        }


def _stats_for(db: Session, user_id) -> UserStats:
    stats = db.get(UserStats, user_id)
    if stats is None:
        stats = UserStats(user_id=user_id)
        db.add(stats)
        db.flush()
    return stats


def _streak_row(db: Session, user_id) -> Streak:
    row = db.get(Streak, user_id)
    if row is None:
        row = Streak(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def _to_state(row: Streak) -> streaks.StreakState:
    return streaks.StreakState(
        current=row.current,
        longest=row.longest,
        last_active_local_date=row.last_active_local_date,
        freezes_available=row.freezes_available,
        freeze_used_dates=tuple(row.freeze_used_dates or ()),
        last_rollover_local_date=row.last_rollover_local_date,
    )


def _apply_state(row: Streak, state: streaks.StreakState) -> None:
    row.current = state.current
    row.longest = state.longest
    row.last_active_local_date = state.last_active_local_date
    row.freezes_available = state.freezes_available
    row.freeze_used_dates = list(state.freeze_used_dates)
    row.last_rollover_local_date = state.last_rollover_local_date


def snapshot(db: Session, user_id) -> StatsSnapshot:
    stats = _stats_for(db, user_id)
    streak = _streak_row(db, user_id)
    return StatsSnapshot(
        total_xp=stats.total_xp,
        level=stats.level,
        lessons_done=stats.lessons_done,
        answers_correct=stats.answers_correct,
        answers_total=stats.answers_total,
        current_streak=streak.current,
        longest_streak=streak.longest,
    )


def evaluate_badges(db: Session, user_id) -> list[dict]:
    """Award any badge the learner now qualifies for. Returns the new ones."""
    stats = snapshot(db, user_id)
    already = {
        b for b in db.scalars(select(UserBadge.badge_id).where(UserBadge.user_id == user_id))
    }
    earned = []
    for badge in db.scalars(select(Badge).order_by(Badge.sort_order)):
        if badge.id in already:
            continue
        try:
            qualifies = evaluate(badge.rule, stats)
        except BadgeRuleError:
            # A malformed badge row must not break a lesson submission.
            continue
        if qualifies:
            db.add(UserBadge(user_id=user_id, badge_id=badge.id))
            earned.append(
                {
                    "slug": badge.slug,
                    "title": badge.title,
                    "description": badge.description,
                    "art_key": badge.art_key,
                }
            )
    return earned


def award_xp(
    db: Session,
    user: User,
    amount: int,
    source: str,
    source_id=None,
    now: datetime | None = None,
    correct: bool | None = None,
    lesson_completed: bool = False,
) -> Rewards:
    """Append XP and cascade streak + badge updates. Caller commits."""
    now = now or datetime.now(UTC)
    today = streaks.local_date(now, user.timezone)

    streak_row = _streak_row(db, user.id)
    before = _to_state(streak_row)
    after = streaks.record_activity(before, today)
    streak_extended = after.current > before.current
    _apply_state(streak_row, after)

    # A streak bonus rides along the first award of each local day.
    bonus = leveling.streak_bonus(after.current) if streak_extended else 0
    total_award = amount + bonus

    db.add(
        XpEvent(user_id=user.id, amount=amount, source=source, source_id=source_id)
    )
    if bonus:
        db.add(
            XpEvent(user_id=user.id, amount=bonus, source="streak_bonus", source_id=None)
        )

    stats = _stats_for(db, user.id)
    previous_level = stats.level
    stats.total_xp += total_award
    stats.level = leveling.level_for_xp(stats.total_xp)
    if correct is not None:
        stats.answers_total += 1
        if correct:
            stats.answers_correct += 1
    if lesson_completed:
        stats.lessons_done += 1
    db.flush()

    return Rewards(
        xp_awarded=total_award,
        total_xp=stats.total_xp,
        level=stats.level,
        leveled_up=stats.level > previous_level,
        streak=after.current,
        streak_extended=streak_extended,
        new_badges=evaluate_badges(db, user.id),
    )
