"""Server-side feature policy, changeable without a deploy.

Some decisions need to change faster than a release cycle — turning a feature
off after a problem, or turning one on once a compliance question is settled.
Those live here as rows, editable from the admin UI.

Values are cached briefly per Lambda container: a warm container would
otherwise re-query on every request, and a minute of staleness is acceptable
for a setting a human changes.
"""
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import PolicyFlag

CACHE_TTL_SECONDS = 60
_cache: dict[str, tuple[float, object]] = {}

# Defaults applied when a flag has never been set. Anything safety-relevant
# defaults to the conservative option.
DEFAULTS: dict[str, object] = {
    "signups.enabled": True,
    "leagues.enabled": True,
}


def get(db: Session, key: str, default=None):
    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    row = db.get(PolicyFlag, key)
    if row is None:
        value = DEFAULTS.get(key, default)
    else:
        value = row.value.get("value") if isinstance(row.value, dict) else row.value
    _cache[key] = (now, value)
    return value


def get_bool(db: Session, key: str, default: bool = False) -> bool:
    return bool(get(db, key, default))


def set_flag(db: Session, key: str, value) -> PolicyFlag:
    row = db.get(PolicyFlag, key)
    if row is None:
        row = PolicyFlag(key=key, value={"value": value})
        db.add(row)
    else:
        row.value = {"value": value}
    _cache.pop(key, None)
    return row


def all_flags(db: Session) -> dict:
    """Every known flag with its effective value, for the admin screen."""
    stored = {
        row.key: (row.value.get("value") if isinstance(row.value, dict) else row.value)
        for row in db.scalars(select(PolicyFlag))
    }
    return {
        key: {"value": stored.get(key, DEFAULTS[key]), "is_default": key not in stored}
        for key in sorted(set(DEFAULTS) | set(stored))
    }
