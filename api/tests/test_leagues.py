from datetime import date

from app.services.leagues import (
    COHORT_SIZE,
    DEMOTE,
    PROMOTE,
    STAY,
    Standing,
    form_cohorts,
    next_tier_rank,
    rank,
    week_start_for,
)


class TestWeekStart:
    def test_monday_is_its_own_week_start(self):
        assert week_start_for(date(2026, 8, 3)) == date(2026, 8, 3)

    def test_sunday_belongs_to_the_week_that_began_monday(self):
        assert week_start_for(date(2026, 8, 9)) == date(2026, 8, 3)

    def test_every_day_of_a_week_maps_to_the_same_start(self):
        starts = {week_start_for(date(2026, 8, d)) for d in range(3, 10)}
        assert starts == {date(2026, 8, 3)}


class TestRanking:
    def _cohort(self, xps):
        return [Standing(user_id=f"u{i}", xp=xp) for i, xp in enumerate(xps)]

    def test_ranks_by_xp_descending(self):
        result = rank(self._cohort([10, 50, 30]))
        assert [uid for uid, _, _ in result] == ["u1", "u2", "u0"]
        assert [pos for _, pos, _ in result] == [1, 2, 3]

    def test_top_seven_promote_and_bottom_seven_demote(self):
        result = rank(self._cohort(list(range(COHORT_SIZE, 0, -1))))
        outcomes = [outcome for _, _, outcome in result]
        assert outcomes[:7] == [PROMOTE] * 7
        assert outcomes[-7:] == [DEMOTE] * 7
        assert set(outcomes[7:-7]) == {STAY}

    def test_ties_break_deterministically_so_reruns_match(self):
        cohort = self._cohort([20, 20, 20])
        assert rank(cohort) == rank(list(reversed(cohort)))

    def test_zero_xp_is_never_promoted(self):
        """Someone who did nothing must not rise on an empty cohort."""
        result = rank(self._cohort([0, 0, 0]))
        assert PROMOTE not in [outcome for _, _, outcome in result]

    def test_small_cohort_prefers_promotion_over_demotion(self):
        """With fewer members than the two bands combined, the leader must not
        be both promoted and demoted."""
        result = rank(self._cohort([100, 50, 10]))
        assert result[0][2] == PROMOTE

    def test_empty_cohort_is_handled(self):
        assert rank([]) == []


class TestTierMovement:
    def test_promotion_rises_one_tier(self):
        assert next_tier_rank(2, PROMOTE, max_rank=6) == 3

    def test_demotion_falls_one_tier(self):
        assert next_tier_rank(2, DEMOTE, max_rank=6) == 1

    def test_staying_holds(self):
        assert next_tier_rank(2, STAY, max_rank=6) == 2

    def test_cannot_rise_above_the_top_tier(self):
        assert next_tier_rank(6, PROMOTE, max_rank=6) == 6

    def test_cannot_fall_below_the_bottom_tier(self):
        assert next_tier_rank(1, DEMOTE, max_rank=6) == 1


class TestCohortFormation:
    def test_splits_into_cohorts_of_the_target_size(self):
        members = [(f"u{i}", 100 - i) for i in range(60)]
        cohorts = form_cohorts(members, size=25)
        assert [len(c) for c in cohorts] == [25, 25, 10]

    def test_cohorts_are_activity_matched(self):
        """The most active learners share a cohort, so nobody faces a field
        they cannot possibly beat."""
        members = [(f"u{i}", i) for i in range(50)]
        cohorts = form_cohorts(members, size=25)
        top = cohorts[0]
        assert "u49" in top and "u25" in top
        assert "u0" not in top

    def test_a_lone_straggler_is_folded_into_the_previous_cohort(self):
        """A cohort of one is a leaderboard with a single name on it."""
        members = [(f"u{i}", 100 - i) for i in range(26)]
        cohorts = form_cohorts(members, size=25)
        assert len(cohorts) == 1
        assert len(cohorts[0]) == 26

    def test_exact_multiple_is_not_merged(self):
        members = [(f"u{i}", 100 - i) for i in range(50)]
        assert [len(c) for c in form_cohorts(members, size=25)] == [25, 25]

    def test_no_members_yields_no_cohorts(self):
        assert form_cohorts([]) == []

    def test_every_member_lands_in_exactly_one_cohort(self):
        members = [(f"u{i}", 100 - i) for i in range(137)]
        cohorts = form_cohorts(members, size=25)
        placed = [uid for cohort in cohorts for uid in cohort]
        assert sorted(placed) == sorted(uid for uid, _ in members)
        assert len(placed) == len(set(placed))
