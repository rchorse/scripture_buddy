# Data retention schedule — ScriptureBuddy

Required by the 2026 amended COPPA rule: personal information may be retained
only as long as reasonably necessary for the purpose it was collected, and never
indefinitely.

Last updated: 2026-08-03. Reviewed annually.

## Principle

Data lives while the account lives. A deletion request disables the account
immediately and triggers an irreversible purge after a 30-day grace period.
Nothing about a child is kept "just in case".

## Schedule

| Data | Table(s) | Retention | Deleted by |
|---|---|---|---|
| Account identity | `core.users` | Life of account | Anonymized on purge (row kept for audit FK integrity; username, birth date, and Cognito link erased) |
| Sign-in credentials | AWS Cognito | Life of account | `retention_sweep` deletes the Cognito user |
| Family membership | `core.family_members` | Life of account | Deleted on purge |
| Learning progress | `srs.cards`, `srs.review_logs` | Life of account | Deleted on purge |
| Gamification | `game.xp_events`, `game.user_stats`, `game.streaks`, `game.user_badges`, `game.league_members` | Life of account | Deleted on purge |
| Reading position | `core.reading_positions` | Life of account | Deleted on purge |
| Push tokens | `core.devices` | Life of account, or until the device is removed | Deleted on purge |
| Entitlements | `core.entitlements` | Life of account | Deleted on purge |
| Exercise flags | `content.exercise_flags` | Life of account | Deleted on purge |
| Consent evidence (signed forms, when used) | S3 `consents/` prefix | Life of account | Deleted on purge |
| Consent tokens | `core.parental_consents.confirm_token_hash` | 72 hours, or until used | Cleared on use or expiry |
| **Consent records** | `core.parental_consents` | **Retained after purge** | — |
| **Consent audit trail** | `core.consent_audit` | **Retained after purge** | — |

## Why the consent trail is retained

COPPA requires an operator to be able to demonstrate that verifiable parental
consent was obtained. Destroying that record on deletion would destroy the
evidence that the account was operated lawfully and that the deletion request
was honoured.

What is retained is deliberately minimal: consent state transitions, timestamps,
which scope, and a **masked** parent email (e.g. `na***@example.com`). No child
content, no learning data, no full email address. The child's user row is
anonymized, so the retained consent rows point at an identifier that no longer
resolves to a person.

If a parent specifically requests erasure of the consent record itself, escalate
— that is a legal judgement call, not an operational one.

## Operational notes

- The purge runs daily via EventBridge (`{"task": "retention_sweep"}`).
- To re-run a missed day: `{"task": "retention_sweep", "as_of": "YYYY-MM-DD"}`.
  This requires AWS credentials and is not reachable from the public API.
- Purges are logged with per-table row counts for audit.
