"""Display-name screening.

Display names are the only user-visible free text in the app — there is no
chat, no profile bio, no comments. That makes this the single place where one
learner's words reach another, so it gets screened before anyone sees it.

Two concerns, weighted by age:

- **All ages:** offensive content, slurs, sexual or violent language, and
  impersonation of staff.
- **Under-13 additionally:** *personal information*. A child (or a well-meaning
  parent) may type a real name, school, town, or social handle into a display
  name. Because an under-13 name can be seen by unrelated learners in a league
  cohort, that would be a disclosure of personal information about a child.

**Fail-closed.** If the check errors, times out, or returns something
unparseable, the name is held rather than shown. A brief delay in a nickname
appearing is a much smaller harm than a child's real name being published.
"""
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

SECRET_ID = "scripturebuddy/anthropic-api-key"
MODEL = "claude-haiku-4-5"
MAX_NAME_LENGTH = 24

# Outcomes
OK = "ok"
FLAGGED = "flagged"
PENDING = "pending"

_ALL_AGES_RULES = """- slurs, hate speech, or harassment
- sexual, violent, or drug-related content
- profanity or obvious evasions of it (leetspeak, spacing, homoglyphs)
- impersonating staff or the app itself (e.g. "Admin", "ScriptureBuddy Team",
  "Moderator", "Support")
- promoting an external website, product, or social account"""

_CHILD_RULES = """- a real first-and-last name, or anything that reads like a real full name
- a school, church congregation, team, club, town, city, or neighbourhood
- a street address, phone number, or email address
- a social media handle or username from another service
- a specific age, birth year, or grade level
- anything else that could help a stranger identify or locate this specific child"""


def _api_key() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    client = boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-west-2")
    )
    secret = client.get_secret_value(SecretId=SECRET_ID)["SecretString"]
    try:
        return json.loads(secret)["api_key"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return secret.strip()


def basic_checks(name: str) -> str | None:
    """Cheap deterministic rejections, before spending a model call."""
    stripped = name.strip()
    if not stripped:
        return "Display name cannot be empty."
    if len(stripped) > MAX_NAME_LENGTH:
        return f"Display name must be {MAX_NAME_LENGTH} characters or fewer."
    if "@" in stripped:
        return "Display name cannot contain '@'."
    if any(ch.isdigit() for ch in stripped) and sum(
        ch.isdigit() for ch in stripped
    ) >= 7:
        # Long digit runs are phone numbers far more often than nicknames.
        return "Display name cannot contain a phone number."
    if "://" in stripped or "www." in stripped.lower():
        return "Display name cannot contain a web address."
    return None


def screen(name: str, is_child: bool) -> dict:
    """Return {status, reason}. status is ok | flagged | pending.

    `pending` means we could not decide — the caller must not show the name.
    """
    problem = basic_checks(name)
    if problem:
        return {"status": FLAGGED, "reason": problem}

    rules = _ALL_AGES_RULES
    if is_child:
        rules += "\n" + _CHILD_RULES

    audience = (
        "a child under 13, whose display name can be seen by other learners"
        if is_child
        else "a teenager or adult"
    )
    prompt = f"""You are screening a display name for a scripture-study app used by families.

The name belongs to {audience}.

Reject the name if it contains any of the following:
{rules}

Ordinary nicknames, scripture references, virtues, animals, and playful
invented words are all fine. Do not reject a name merely for being unusual,
for being a common given name on its own (like "Sam" or "Ruth"), or for being
in another language.

Display name to screen: {name!r}

Respond with JSON only: {{"allow": true}} or
{{"allow": false, "reason": "<short reason for the user, one sentence>"}}"""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=_api_key())
        message = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in message.content if b.type == "text").strip()
        # Tolerate a fenced block around the JSON.
        if raw.startswith("```"):
            raw = raw.split("```")[1].removeprefix("json").strip()
        verdict = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — fail closed, never fail open
        logger.warning("display name screening unavailable: %s", exc)
        return {
            "status": PENDING,
            "reason": "We could not check this name yet. It will appear once reviewed.",
        }

    if verdict.get("allow") is True:
        return {"status": OK, "reason": ""}
    return {
        "status": FLAGGED,
        "reason": verdict.get("reason") or "That name can't be used here.",
    }


def public_name(user) -> str:
    """What other learners see.

    Anything not cleared falls back to the username, which for a child was
    chosen by their parent and is validated to be alphanumeric.
    """
    if user.display_name and user.display_name_status == OK:
        return user.display_name
    return user.username
