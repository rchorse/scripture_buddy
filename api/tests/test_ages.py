"""Age bracket rules.

These decide whether COPPA obligations attach to an account, so the boundary
days get explicit coverage — an off-by-one here is a compliance failure, not a
cosmetic bug.
"""
from datetime import date

import pytest

from app.services.ages import (
    ADULT,
    TEEN,
    UNDER_13,
    InvalidBirthDate,
    age_on,
    bracket_for,
    can_self_register,
    is_minor,
    requires_verifiable_parental_consent,
    turns_18_on,
    validate_birth_date,
)

TODAY = date(2026, 8, 3)


class TestAgeOn:
    def test_birthday_already_passed_this_year(self):
        assert age_on(date(2010, 1, 1), TODAY) == 16

    def test_birthday_later_this_year_has_not_counted_yet(self):
        assert age_on(date(2010, 12, 31), TODAY) == 15

    def test_birthday_is_today(self):
        assert age_on(date(2010, 8, 3), TODAY) == 16

    def test_day_before_birthday(self):
        assert age_on(date(2010, 8, 4), TODAY) == 15

    def test_leap_day_birthday_counts_from_march_first_in_common_years(self):
        born = date(2012, 2, 29)
        # 2026 is not a leap year: on 28 Feb they are still 13.
        assert age_on(born, date(2026, 2, 28)) == 13
        # On 1 March they turn 14.
        assert age_on(born, date(2026, 3, 1)) == 14

    def test_future_birth_date_is_rejected(self):
        with pytest.raises(InvalidBirthDate):
            age_on(date(2027, 1, 1), TODAY)


class TestBracket:
    def test_twelve_is_under_13(self):
        assert bracket_for(date(2014, 1, 1), TODAY) == UNDER_13

    def test_the_day_before_the_thirteenth_birthday_is_still_under_13(self):
        # Turns 13 on 2026-08-04.
        assert bracket_for(date(2013, 8, 4), TODAY) == UNDER_13

    def test_the_thirteenth_birthday_becomes_teen(self):
        assert bracket_for(date(2013, 8, 3), TODAY) == TEEN

    def test_seventeen_is_still_a_teen(self):
        assert bracket_for(date(2009, 1, 1), TODAY) == TEEN

    def test_the_day_before_the_eighteenth_birthday_is_still_a_teen(self):
        assert bracket_for(date(2008, 8, 4), TODAY) == TEEN

    def test_the_eighteenth_birthday_becomes_adult(self):
        assert bracket_for(date(2008, 8, 3), TODAY) == ADULT

    def test_implausible_age_is_rejected(self):
        with pytest.raises(InvalidBirthDate):
            bracket_for(date(1800, 1, 1), TODAY)

    def test_validate_accepts_today_as_a_birth_date(self):
        assert validate_birth_date(TODAY, TODAY) == TODAY


class TestObligations:
    def test_only_under_13_requires_verifiable_consent(self):
        assert requires_verifiable_parental_consent(UNDER_13)
        assert not requires_verifiable_parental_consent(TEEN)
        assert not requires_verifiable_parental_consent(ADULT)

    def test_under_13_cannot_self_register(self):
        assert not can_self_register(UNDER_13)
        assert can_self_register(TEEN)
        assert can_self_register(ADULT)

    def test_both_under_13_and_teens_are_minors(self):
        assert is_minor(UNDER_13)
        assert is_minor(TEEN)
        assert not is_minor(ADULT)


class TestTurns18:
    def test_ordinary_birth_date(self):
        assert turns_18_on(date(2010, 6, 15)) == date(2028, 6, 15)

    def test_leap_day_birth_date_resolves_to_march_first(self):
        # 2030 is not a leap year, so 29 Feb 2012 + 18 years has no exact date.
        assert turns_18_on(date(2012, 2, 29)) == date(2030, 3, 1)
