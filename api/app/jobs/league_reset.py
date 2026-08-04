"""Weekly league reset — Monday 00:05 UTC.

Two phases: finalize last week's cohorts (rank, promote, demote), then draw new
cohorts for the week that just started.

Idempotent: a cohort whose members already have outcomes is skipped, and a
learner already placed in this week's cohort is not placed again. The schedule
can fire twice without doubling anyone up.
"""
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models.core import User
from app.models.game import LeagueCohort, LeagueMember, LeagueTier, XpEvent
from app.services import friendships, leagues
from app.services.friendships import FriendshipError

logger = logging.getLogger(__name__)


def _xp_between(session: Session, user_ids, start: datetime, end: datetime) -> dict:
    if not user_ids:
        return {}
    return dict(
        session.execute(
            select(XpEvent.user_id, func.coalesce(func.sum(XpEvent.amount), 0))
            .where(
                XpEvent.user_id.in_(user_ids),
                XpEvent.awarded_at >= start,
                XpEvent.awarded_at < end,
            )
            .group_by(XpEvent.user_id)
        ).all()
    )


def _finalize(session: Session, this_week: date) -> dict:
    """Rank and close every cohort from before this week."""
    counts = {"cohorts_finalized": 0, "promoted": 0, "demoted": 0}
    open_cohorts = session.scalars(
        select(LeagueCohort).where(LeagueCohort.week_start < this_week)
    ).all()

    for cohort in open_cohorts:
        members = session.scalars(
            select(LeagueMember).where(LeagueMember.cohort_id == cohort.id)
        ).all()
        if not members or all(m.outcome is not None for m in members):
            continue  # already finalized

        start = datetime.combine(cohort.week_start, datetime.min.time(), tzinfo=UTC)
        end = start + timedelta(days=7)
        totals = _xp_between(session, [m.user_id for m in members], start, end)

        standings = [
            leagues.Standing(user_id=m.user_id, xp=int(totals.get(m.user_id, 0)))
            for m in members
        ]
        by_user = {m.user_id: m for m in members}
        for user_id, position, outcome in leagues.rank(standings):
            member = by_user[user_id]
            member.final_rank = position
            member.outcome = outcome
            if outcome == leagues.PROMOTE:
                counts["promoted"] += 1
            elif outcome == leagues.DEMOTE:
                counts["demoted"] += 1
        counts["cohorts_finalized"] += 1
    return counts


def _current_tier_rank(session: Session, user_id, tiers_by_id: dict) -> int:
    """Where this learner sits now, from their most recent finished cohort."""
    row = session.execute(
        select(LeagueMember, LeagueCohort.tier_id, LeagueCohort.week_start)
        .join(LeagueCohort, LeagueCohort.id == LeagueMember.cohort_id)
        .where(LeagueMember.user_id == user_id, LeagueMember.outcome.isnot(None))
        .order_by(LeagueCohort.week_start.desc())
        .limit(1)
    ).first()
    if row is None:
        return 1  # everyone starts at the bottom tier
    member, tier_id, _ = row
    return leagues.next_tier_rank(
        tiers_by_id[tier_id], member.outcome, max_rank=max(tiers_by_id.values())
    )


def league_reset(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    this_week = leagues.week_start_for(now.date())

    with Session(get_engine()) as session:
        tiers = session.scalars(select(LeagueTier).order_by(LeagueTier.rank)).all()
        if not tiers:
            return {"status": "ok", "note": "no league tiers seeded"}
        tiers_by_id = {t.id: t.rank for t in tiers}
        tier_by_rank = {t.rank: t for t in tiers}

        result = _finalize(session, this_week)
        session.flush()

        # Anyone already drawn for this week stays put.
        already = {
            row
            for row in session.scalars(
                select(LeagueMember.user_id)
                .join(LeagueCohort, LeagueCohort.id == LeagueMember.cohort_id)
                .where(LeagueCohort.week_start == this_week)
            )
        }

        window_start = now - timedelta(days=leagues.ACTIVITY_WINDOW_DAYS)
        active_ids = [
            uid
            for uid in session.scalars(
                select(XpEvent.user_id)
                .where(XpEvent.awarded_at >= window_start)
                .group_by(XpEvent.user_id)
            )
            if uid not in already
        ]

        # Leagues show a display name to learners outside your friends, so the
        # same eligibility gate as the rest of social applies.
        eligible = []
        for user in session.scalars(select(User).where(User.id.in_(active_ids))) if active_ids else []:
            if user.status != "active":
                continue
            try:
                friendships.assert_may_socialize(session, user)
            except FriendshipError:
                continue
            eligible.append(user.id)

        recent = _xp_between(session, eligible, window_start, now)
        by_tier: dict[int, list] = {}
        for user_id in eligible:
            tier_rank = _current_tier_rank(session, user_id, tiers_by_id)
            by_tier.setdefault(tier_rank, []).append(
                (user_id, int(recent.get(user_id, 0)))
            )

        created = 0
        placed = 0
        for tier_rank, members in by_tier.items():
            tier = tier_by_rank.get(tier_rank) or tier_by_rank[1]
            for group in leagues.form_cohorts(members):
                cohort = LeagueCohort(tier_id=tier.id, week_start=this_week)
                session.add(cohort)
                session.flush()
                for user_id in group:
                    session.add(
                        LeagueMember(cohort_id=cohort.id, user_id=user_id)
                    )
                    placed += 1
                created += 1

        session.commit()

    return {
        "status": "ok",
        "week_start": this_week.isoformat(),
        **result,
        "cohorts_created": created,
        "learners_placed": placed,
    }
