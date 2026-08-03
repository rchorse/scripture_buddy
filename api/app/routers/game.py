from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.principal import get_current_user
from app.models.core import User
from app.models.game import Badge, UserBadge
from app.services import leveling, streaks
from app.services.gamification import _stats_for, _streak_row

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/me")
def my_progress(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Everything the home screen shows: level, XP, streak, badges."""
    stats = _stats_for(db, user.id)
    streak = _streak_row(db, user.id)
    db.commit()

    today = streaks.local_date(datetime.now(UTC), user.timezone)
    earned = {
        row.badge_id: row.earned_at
        for row in db.scalars(select(UserBadge).where(UserBadge.user_id == user.id))
    }
    badges = [
        {
            "slug": badge.slug,
            "title": badge.title,
            "description": badge.description,
            "art_key": badge.art_key,
            "earned": badge.id in earned,
            "earned_at": earned[badge.id].isoformat() if badge.id in earned else None,
        }
        for badge in db.scalars(select(Badge).order_by(Badge.sort_order))
    ]

    return {
        **leveling.progress(stats.total_xp),
        "lessons_done": stats.lessons_done,
        "answers_correct": stats.answers_correct,
        "answers_total": stats.answers_total,
        "accuracy": (
            stats.answers_correct / stats.answers_total if stats.answers_total else 0.0
        ),
        "streak": {
            "current": streak.current,
            "longest": streak.longest,
            "freezes_available": streak.freezes_available,
            "practised_today": streak.last_active_local_date == today,
            "at_risk": streak.current > 0 and streak.last_active_local_date != today,
        },
        "badges": badges,
        "badges_earned": len(earned),
    }
