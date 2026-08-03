"""Streak rules, computed in the learner's own timezone.

The whole feature hinges on one thing: "today" means the learner's local
calendar day, never UTC's. Someone in Auckland practising at 9am local is on a
different UTC date than someone in Los Angeles doing the same, and both must
keep their streak.

Pure functions over a `StreakState` so DST transitions and timezone extremes
can be tested at fixed clocks.
"""
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"


@dataclass(frozen=True)
class StreakState:
    current: int = 0
    longest: int = 0
    last_active_local_date: date | None = None
    freezes_available: int = 1
    freeze_used_dates: tuple[date, ...] = ()
    last_rollover_local_date: date | None = None


def zone_for(timezone_name: str | None) -> ZoneInfo:
    """Resolve an IANA name, falling back to UTC rather than raising.

    A bad timezone must never break practising — it just means the learner's
    day boundary is wrong until they fix their profile.
    """
    try:
        return ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def local_date(now: datetime, timezone_name: str | None) -> date:
    """The learner's current calendar date."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(zone_for(timezone_name)).date()


def record_activity(state: StreakState, today: date) -> StreakState:
    """Called when the learner earns XP. Extends or starts a streak."""
    last = state.last_active_local_date
    if last == today:
        return state  # already counted today
    if last is not None and last == today - timedelta(days=1):
        current = state.current + 1
    elif last is not None and _bridged_by_freeze(state, last, today):
        # Missed days were already covered by freezes at rollover.
        current = state.current + 1
    else:
        current = 1  # first day, or the streak had lapsed
    return replace(
        state,
        current=current,
        longest=max(state.longest, current),
        last_active_local_date=today,
    )


def _bridged_by_freeze(state: StreakState, last: date, today: date) -> bool:
    """True when every day between last activity and today was frozen."""
    gap_days = (today - last).days
    if gap_days < 2:
        return False
    missed = {last + timedelta(days=i) for i in range(1, gap_days)}
    return missed.issubset(set(state.freeze_used_dates))


def roll_over(state: StreakState, today: date) -> tuple[StreakState, str]:
    """Apply the day boundary. Returns (state, outcome).

    Called once per learner per local day. Outcomes:
      "noop"    — already rolled over today, or nothing to decide
      "kept"    — they practised yesterday; streak intact
      "frozen"  — they missed yesterday but a freeze covered it
      "reset"   — they missed yesterday with no freeze; streak cleared
    """
    if state.last_rollover_local_date == today:
        return state, "noop"

    yesterday = today - timedelta(days=1)
    state = replace(state, last_rollover_local_date=today)

    if state.current == 0 or state.last_active_local_date is None:
        return state, "noop"
    if state.last_active_local_date >= yesterday:
        return state, "kept"
    if yesterday in state.freeze_used_dates:
        return state, "noop"  # already frozen by an earlier pass

    if state.freezes_available > 0:
        return (
            replace(
                state,
                freezes_available=state.freezes_available - 1,
                freeze_used_dates=(*state.freeze_used_dates, yesterday),
            ),
            "frozen",
        )
    return replace(state, current=0), "reset"


def is_at_risk(state: StreakState, today: date) -> bool:
    """Streak alive but not yet practised today — the reminder trigger."""
    return state.current > 0 and state.last_active_local_date != today
