"""Age brackets, computed server-side from birth_date.

COPPA obligations attach to a specific age boundary, so this is the one place
age is decided. The client never tells us how old someone is — it sends a birth
date at signup and the server derives everything from it, because a
client-supplied "I am over 13" flag is worth nothing.

Brackets:
  under_13  full COPPA: verifiable parental consent before any PI collection
  teen      13-17: parental approval still required for social features
  adult     18+
"""
from datetime import date

UNDER_13 = "under_13"
TEEN = "teen"
ADULT = "adult"

COPPA_AGE = 13
ADULT_AGE = 18
# Oldest plausible birth date, to catch typos like year 1080.
MAX_AGE = 120


class InvalidBirthDate(ValueError):
    pass


def age_on(birth_date: date, today: date) -> int:
    """Completed years of age. Handles leap-day birthdays."""
    if birth_date > today:
        raise InvalidBirthDate("birth date is in the future")
    years = today.year - birth_date.year
    # Not yet had this year's birthday? A 29 Feb birthday counts on 1 Mar in
    # non-leap years, which `(month, day)` comparison gives us for free.
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def validate_birth_date(birth_date: date, today: date) -> date:
    if birth_date > today:
        raise InvalidBirthDate("birth date is in the future")
    if age_on(birth_date, today) > MAX_AGE:
        raise InvalidBirthDate("birth date is implausibly old")
    return birth_date


def bracket_for(birth_date: date, today: date) -> str:
    age = age_on(validate_birth_date(birth_date, today), today)
    if age < COPPA_AGE:
        return UNDER_13
    if age < ADULT_AGE:
        return TEEN
    return ADULT


def is_minor(bracket: str) -> bool:
    return bracket in (UNDER_13, TEEN)


def requires_verifiable_parental_consent(bracket: str) -> bool:
    """COPPA's trigger — only under-13 requires *verifiable* consent."""
    return bracket == UNDER_13


def can_self_register(bracket: str) -> bool:
    """Under-13s cannot create their own account; a parent must."""
    return bracket != UNDER_13


def turns_18_on(birth_date: date) -> date:
    """When parental oversight ends. Used to expire parent access."""
    try:
        return birth_date.replace(year=birth_date.year + ADULT_AGE)
    except ValueError:
        # 29 February — treat the 18th birthday as 1 March.
        return date(birth_date.year + ADULT_AGE, 3, 1)
