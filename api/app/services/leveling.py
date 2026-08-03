"""XP → level curve.

Deliberately sub-linear so early levels come quickly (the first few are the
ones that hook a new learner) and later ones stretch out. Pure arithmetic so
the curve can be re-tuned without touching stored data — levels are always
derived from `total_xp`, never stored as truth.
"""
import math

XP_PER_LEVEL_BASE = 100
CURVE_EXPONENT = 0.6

# XP awards
XP_CORRECT_ANSWER = 10
XP_INCORRECT_ANSWER = 2  # effort still counts, just less
XP_LESSON_COMPLETE = 20
XP_STREAK_BONUS_PER_DAY = 2
XP_STREAK_BONUS_CAP = 50


def level_for_xp(total_xp: int) -> int:
    if total_xp < 0:
        raise ValueError("total_xp cannot be negative")
    return int((total_xp / XP_PER_LEVEL_BASE) ** CURVE_EXPONENT) + 1


def xp_for_level(level: int) -> int:
    """Minimum XP that actually yields `level`.

    Rounds up: truncating leaves a value one XP short of the threshold, so
    xp_for_level would name an amount that still reports the previous level.
    """
    if level <= 1:
        return 0
    exact = ((level - 1) ** (1 / CURVE_EXPONENT)) * XP_PER_LEVEL_BASE
    candidate = math.ceil(exact)
    # Guard against float drift at the boundary in either direction.
    while level_for_xp(candidate) < level:
        candidate += 1
    while candidate > 0 and level_for_xp(candidate - 1) >= level:
        candidate -= 1
    return candidate


def progress(total_xp: int) -> dict:
    """Level plus how far into it the learner is, for the progress bar."""
    level = level_for_xp(total_xp)
    floor_xp = xp_for_level(level)
    next_xp = xp_for_level(level + 1)
    span = max(next_xp - floor_xp, 1)
    return {
        "level": level,
        "total_xp": total_xp,
        "level_floor_xp": floor_xp,
        "next_level_xp": next_xp,
        "xp_into_level": total_xp - floor_xp,
        "xp_to_next_level": max(next_xp - total_xp, 0),
        "fraction": min(max((total_xp - floor_xp) / span, 0.0), 1.0),
    }


def streak_bonus(streak_days: int) -> int:
    """Daily bonus for keeping a streak, capped so it can't dwarf real work."""
    if streak_days <= 1:
        return 0
    return min(streak_days * XP_STREAK_BONUS_PER_DAY, XP_STREAK_BONUS_CAP)
