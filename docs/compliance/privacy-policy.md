# ScriptureBuddy Privacy Policy

**Draft — not yet reviewed by a lawyer, and not yet published.** Everything
below describes what the code actually does today; see "Known gaps" at the end
for the places where that is not yet true, which must close before this is
posted.

**Last updated:** _(fill in on publication)_
**Contact:** _(fill in — a monitored address is required by both app stores and
by COPPA)_

---

## The short version

ScriptureBuddy helps people read and memorise scripture. We collect the least we
can get away with, we show no ads, and we never sell your information.

**There is no chat, no messaging, and no way for users to send each other text.**
The only thing one user can see another write is a display name, and every
display name is screened before anyone else sees it.

Accounts for children under 13 are deliberately narrower than adult accounts: we
do not collect an email address, phone number, real name, or location for a
child, and there are no database columns to store them in.

## What we collect

### Adults and teenagers (13+)

| Data | Why |
|---|---|
| Username | Signing in; visible to friends |
| Email address | Confirming your account and resetting your password |
| Password | Signing in (stored by AWS Cognito, never by us in readable form) |
| Date of birth | Applying the right protections for your age. Stored once and not editable in the app |
| Time zone | Working out when your day ends, so streaks are correct |
| Display name (optional) | What friends see instead of your username |
| Progress: lessons, answers, XP, streaks, review schedule | Running the app and showing you how you are doing |
| Friend relationships and blocks | The friends list and leaderboards |

### Children under 13

A parent or guardian creates the account. We collect:

- a **username** the parent chooses
- their **date of birth**, used only to apply the right protections
- their **time zone**
- an optional **display name**, screened before anyone sees it
- their **progress** in the app

We do **not** collect a child's email address, phone number, real name,
photograph, voice, precise location, or any persistent identifier used for
advertising.

## How we use it

To run the app: show you the right lessons, mark your answers, schedule your
reviews, keep your streak, and show leaderboards among friends.

We do not use your information to advertise to you, and we do not sell or rent
it. We do not use your personal information to train AI models.

## Who else sees it

- **Amazon Web Services** hosts the app and stores its data (United States).
  AWS Cognito holds sign-in credentials.
- **Anthropic** provides the model that screens display names. When a display
  name is submitted, that text is sent to Anthropic to check it. For a child's
  account this happens **only if a parent has consented to AI processing**;
  without that consent the child's public name is simply their username.
  Practice questions are generated ahead of time from scripture text alone — no
  user information is involved.

Other users see only your display name (or username) and your position on a
leaderboard, and only if you are their friend.

We may disclose information if the law requires it.

## Parents: your rights

At any time, from the Family screen or by contacting us, you can:

- **See** what we have collected about your child
- **Withdraw consent** for any purpose, individually. Withdrawing consent for
  friends removes their access to friends and leaderboards; withdrawing consent
  for AI processing stops us sending their display name for screening
- **Delete** the account. Deletion is scheduled immediately and the data is
  irreversibly erased after 30 days, during which you can cancel it
- **Refuse** any further collection, by deleting the account

Consent is recorded per purpose (`account`, `ai_processing`, `social`), and only
`account` is required to use the app at all. Our record of consent decisions is
append-only and outlives the account, because we have to be able to show what
was agreed and when.

## How long we keep things

See `data-retention-schedule.md`. In summary: account data lives as long as the
account does; a deleted account is purged 30 days after the request; the consent
audit trail is kept indefinitely because COPPA requires us to evidence consent.

## Security

Data is encrypted in transit and at rest. The database is not reachable from the
public internet. Access to production data is limited to the operator of the
service. Our written security program is described in `coppa-program.md`.

## Changes

If we change how we use information already collected from a child, we will ask
the parent to consent again rather than relying on the original consent.

## Children's privacy (COPPA)

ScriptureBuddy is intended for general audiences and is used by children under
13 with a parent's involvement. We follow the Children's Online Privacy
Protection Act:

- A neutral age screen runs before any account is created. It stores nothing.
- A child under 13 cannot create their own account and is never shown a signup
  form.
- A parent creates the account and receives an email asking them to confirm.
  The account cannot be used until they do.
- We collect no more from a child than is reasonably necessary to take part.
- A parent may review, withdraw consent, or delete at any time.

---

## Known gaps — must close before publishing

1. **Contact address.** Both stores and COPPA require a monitored contact point.
   Not yet chosen.
2. **Not hosted anywhere.** This document has to be reachable at a stable public
   URL, linked from the app and from both store listings.
3. **Legal review.** In particular the email-plus consent method, and the fact
   that a child's screened display name is visible to unrelated learners in a
   league cohort. Raised in `coppa-program.md` and still open.
4. **SES not configured.** Consent email does not currently send, so the
   parental confirmation step described above cannot complete.
5. **Retention sweep evidence.** The 30-day purge is implemented and was
   verified once by hand; it is not yet covered by an automated test.
