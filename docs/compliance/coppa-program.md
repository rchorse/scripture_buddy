# COPPA compliance program — ScriptureBuddy

**Status: DRAFT — not yet reviewed by legal counsel.** The 2026 amended COPPA
rule requires operators to maintain a *written* children's privacy and security
program. This document is that program. It must be reviewed by counsel before
public launch and re-reviewed at least annually.

Owner: Nathan Starr (sole operator).
Last updated: 2026-08-03.

---

## 1. Scope

ScriptureBuddy is a general-audience scripture-study app that knowingly permits
users under 13, so COPPA applies to those accounts. It is **not** listed in
Apple's Kids Category and is not directed to children as its primary audience;
the under-13 protections below apply to any account whose server-derived age
bracket is `under_13`.

## 2. What we collect, and from whom

### Child accounts (under 13)

| Data | Why | Where |
|---|---|---|
| Username (chosen by the parent) | Sign-in and display | `core.users.username` |
| Birth date | Solely to derive the age bracket and apply protections | `core.users.birth_date` |
| Timezone (IANA) | Streaks must roll over at the child's local midnight | `core.users.timezone` |
| Learning progress (answers, XP, streaks, spaced-repetition state) | The service itself | `game.*`, `srs.*` |

**Deliberately not collected for a child:** email address, phone number, real
name, postal address, geolocation, photographs, audio, video, biometrics, or
persistent identifiers used for advertising. There are **no database columns**
for these on a child record, so no code path can persist them.

### Parent accounts

Email address (held in AWS Cognito, not in our database), used only to obtain
and confirm consent and for account recovery.

## 3. Age determination

- A neutral age gate (`POST /v1/family/age-gate`) collects a birth date **before
  any account exists**. It stores nothing and creates nothing.
- The gate is neutral: it asks for a birth date rather than "are you over 13?",
  which would invite misreporting.
- Under-13 users **cannot self-register**. They are told a parent must create the
  account. No child personal information is collected at this point.
- The age bracket is always derived server-side from `birth_date`
  (`app/services/ages.py`). A client-supplied age is never trusted.

## 4. Verifiable parental consent

**Method: email plus** (`app/services/consent_email.py`).

1. A verified adult creates the child account. We already hold the parent's
   email because they are an account holder.
2. We email the parent a consent notice describing exactly what is collected and
   how it is used, with a one-time link (single-use, 72-hour expiry, stored only
   as a SHA-256 hash).
3. The parent opens the link to consent. The child account is **unusable** until
   this happens — status `pending_consent`, and every authenticated request is
   rejected.
4. **The "plus" step:** a delayed confirmation email (~24h later) tells the
   parent consent was recorded and how to withdraw it, giving an independent
   opportunity to catch a consent they did not give.

**Why this method is appropriate.** The FTC permits a less rigorous method where
the operator does not disclose children's personal information to third parties
or make it publicly available. ScriptureBuddy does neither:

- No chat or messaging of any kind.
- **No social features for under-13 accounts, ever** — a child's display name,
  progress, and existence are never visible to any other user. This is a fixed
  product decision enforced in `app/services/friendships.py`, not a setting.
- No advertising or analytics SDKs; nothing sold or shared.
- AWS and Anthropic act strictly as service providers under contract.

A child's personal information therefore never leaves the operator's control,
which is precisely the condition the lighter method is designed for.
**This determination should still be confirmed by counsel.**

### Per-scope consent

The amended rule requires separate consent for materially different uses.
Consent is recorded **per scope** and is independently revocable:

| Scope | Covers |
|---|---|
| `account` | Creating and using the account. **Required** — without it the account is disabled. |
| `ai_processing` | Sending answer text to Anthropic for grading assistance and content generation. |

There is deliberately **no `social` scope**: under-13 accounts have no social
surface, so there is nothing to consent to. Consent is never used as a condition
of participation beyond what the service requires — a child may use the app with
only `account` consent.

## 5. Parental rights

| Right | How it is exercised | Effect |
|---|---|---|
| Review what we hold | Family screen in the app | Shows the child's data |
| Withdraw consent | Family screen → revoke | Account disabled **immediately** |
| Refuse further collection | Revoke `ai_processing` | That use stops; account still works |
| Delete the child's data | Family screen → delete | Disabled at once; irreversible purge after 30 days |

Parental authority ends automatically at 18 (`require_parent_of` refuses once
the child's derived bracket is `adult`).

## 6. Retention and deletion

- Data is retained only while the account is active. There is no indefinite
  retention.
- A deletion request disables the account immediately and schedules an
  irreversible purge after a **30-day grace period** (so an accidental request
  can be undone).
- The purge (`app/jobs/retention_sweep.py`, daily) deletes all learning data,
  gamification data, family membership, device tokens, entitlements, flags, the
  Cognito user, and any consent evidence in S3. The user row is anonymized
  rather than deleted.
- **Deliberately retained:** the `core.consent_audit` trail and the consent rows
  it references. This is the evidence that consent was lawfully obtained and
  later honoured. It contains no information about the child beyond consent
  state changes and a masked parent email.

See `data-retention-schedule.md` for the per-table schedule.

## 7. Security

- All data in transit is TLS. Data at rest is encrypted (Aurora, S3, Secrets
  Manager defaults).
- The database is in a private VPC with no public route; only the API Lambda can
  reach it, using a dedicated least-privilege Postgres role (`sb_app`).
- Consent evidence is stored in a private S3 bucket with public access blocked,
  reachable only via short-lived presigned URLs.
- Consent tokens are stored only as SHA-256 hashes, are single-use, and expire.
- The Lambda's IAM permissions are scoped to the specific Cognito pool, S3
  bucket, and secrets it needs.
- Admin access requires membership of the Cognito `owner` group.
- **Open item:** enable MFA on the AWS root and IAM accounts, and on the owner's
  Cognito account, before launch.

## 8. Service providers

| Provider | Role | Child data involved |
|---|---|---|
| AWS | Hosting, database, auth, email | All of it, under the AWS DPA |
| Anthropic | Grading assistance, content generation, display-name screening | Answer text only, when `ai_processing` consent is granted. No identifiers are sent. |

Neither is permitted to use the data for their own purposes. **Open item:**
confirm the current API data-usage terms in writing before launch.

## 9. Third parties, advertising, tracking

None. No advertising SDKs, no analytics SDKs, no behavioural profiling, no
selling or sharing of personal information, ever. This is a hard product rule
recorded in `CLAUDE.md`.

## 10. Review

This program is reviewed:
- Before public launch (with counsel).
- At least annually thereafter.
- Whenever a new category of data is collected or a new service provider is
  added.
- **If under-13 social features are ever contemplated** (currently ruled out),
  the consent method must be re-assessed first — the justification for
  email-plus rests partly on nothing about a child being visible to others.

| Date | Reviewer | Outcome |
|---|---|---|
| 2026-08-03 | Owner | Initial draft. **Pending legal review.** |
