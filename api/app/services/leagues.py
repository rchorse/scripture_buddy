"""Weekly leagues: ranking, promotion, and cohort formation.

A league is a cohort of ~25 learners competing on XP for one week. At the end
of the week the top few move up a tier, the bottom few move down, and everyone
is re-drawn into a fresh cohort.

Cohorts are activity-matched: learners are grouped by tier and then by recent
XP, so a cohort feels winnable rather than hopeless. A cohort nobody can win is
worse than no cohort at all.

Pure functions here; the job in jobs/league_reset.py does the database work.
"""
from dataclasses import dataclass
from datetime import date, timedelta

COHORT_SIZE = 25
PROMOTE_COUNT = 7
DEMOTE_COUNT = 7
# Learners with no XP in this window aren't drawn into a cohort — an inactive
# member just occupies a slot someone else could compete for.
ACTIVITY_WINDOW_DAYS = 14

PROMOTE = "promote"
STAY = "stay"
DEMOTE = "demote"


@dataclass(frozen=True)
class Standing:
    user_id: object
    xp: int


def week_start_for(day: date) -> date:
    """Monday of the week containing `day`. Weeks are UTC-aligned."""
    return day - timedelta(days=day.weekday())


def rank(standings: list[Standing]) -> list[tuple[object, int, str]]:
    """Rank a cohort and decide each member's outcome.

    Returns (user_id, final_rank, outcome), best first. Ties are broken
    deterministically by user id so a re-run produces identical results.
    """
    ordered = sorted(standings, key=lambda s: (-s.xp, str(s.user_id)))
    size = len(ordered)
    out = []
    for index, standing in enumerate(ordered):
        position = index + 1
        if position <= PROMOTE_COUNT and standing.xp > 0:
            # Promotion is checked first, so in a cohort smaller than the two
            # bands combined a top finisher is promoted rather than demoted.
            outcome = PROMOTE
        elif position > size - DEMOTE_COUNT:
            outcome = DEMOTE
        else:
            outcome = STAY
        out.append((standing.user_id, position, outcome))
    return out


def next_tier_rank(current_rank: int, outcome: str, max_rank: int) -> int:
    """Where a learner lands next week. Tier 1 is the lowest."""
    if outcome == PROMOTE:
        return min(current_rank + 1, max_rank)
    if outcome == DEMOTE:
        return max(current_rank - 1, 1)
    return current_rank


def form_cohorts(
    ranked_members: list[tuple[object, int]], size: int = COHORT_SIZE
) -> list[list[object]]:
    """Split learners of one tier into activity-matched cohorts.

    `ranked_members` is (user_id, recent_xp). Sorting by recent XP before
    chunking means each cohort contains people of similar activity.
    """
    ordered = [
        uid
        for uid, _ in sorted(ranked_members, key=lambda m: (-m[1], str(m[0])))
    ]
    if not ordered:
        return []

    cohorts = [ordered[i : i + size] for i in range(0, len(ordered), size)]
    # Avoid stranding one or two people alone in a trailing cohort.
    if len(cohorts) > 1 and len(cohorts[-1]) < max(2, size // 5):
        stragglers = cohorts.pop()
        cohorts[-1].extend(stragglers)
    return cohorts
