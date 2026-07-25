# ScriptureBuddy — project conventions

Approved plan: `~/.claude/plans/steady-dreaming-cray.md` (architecture, milestones M0–M7, locked decisions).

## Hard rules
- **No chat/messaging features. Ever.** This was a final product decision; the only user-visible UGC is custom display names (Haiku-checked, fail-closed).
- Under-13 users are supported → full COPPA (2026 rule). Child accounts are username-only: never store email/phone/real-name/geolocation for minors. Age bracket is computed server-side from birth_date, never trusted from the client.
- No ads SDKs. Monetization goes through the `entitlements` table only.
- Clients only see released content (`releases`/`release_items`), never raw `exercises` state.

## Stack
- Flutter app (`app/`), FastAPI on Lambda via Mangum (`api/`), CDK Python (`infra/`), Postgres on shared Aurora Serverless v2 (database `scripturebuddy`, role `sb_app`).
- Postgres schemas are module boundaries: `content`, `core`, `game`, `social`, `mod`, `srs`. One SQLAlchemy models module per schema.
- Admin UI is server-rendered Jinja2/HTMX under `/admin` on the API Lambda (owner-gated via Cognito group `owner`).
- Jobs are EventBridge rules invoking the API Lambda with `{"task": "<name>"}` payloads (see `api/main.py` handler dispatch).

## Conventions
- Python: ruff, pytest; SQLAlchemy 2.0 style; Alembic owns all DDL. Use `python3`, not `python`.
- Follow BlahBlahBudget patterns where they exist (`/home/nathans/blah_blah_budget/` is read-only reference): local pip bundling in CDK, `{"task":"migrate"}` invoke, warmer event, db.py engine bootstrap with Aurora resume retries.
- All PKs are UUIDv7. `xp_events` and `consent_audit` are append-only.
- Timezone-sensitive logic (streaks) always uses the user's IANA timezone server-side.
- Flutter: feature-first directory layout (`lib/features/<feature>/`), no cross-feature imports except through `core/`.
