# Direct notice to parents

The text sent to a parent when consent is requested. The canonical version lives
in `api/app/services/consent_email.py`; this file is the reviewable copy.

COPPA requires the direct notice to state: that we wish to collect personal
information from the child, what we collect, how we use it, that the parent's
consent is required, and how to give or withdraw it.

---

**Subject:** Please confirm consent for {child_username} on ScriptureBuddy

> You asked to create a ScriptureBuddy account for **{child_username}**.
>
> Because they are under 13, US law (COPPA) requires us to confirm that a parent
> or guardian consents before the account can be used.
>
> You are being asked to consent to let them **{what}**.
>
> **What we collect for a child account:** a username you choose, their birth
> date (used only to apply the right protections), their timezone, and their
> progress in the app. We do not collect an email address, phone number, real
> name, or location for a child. We do not show ads, and we never sell or share
> their information.
>
> To give consent, open this link within 72 hours:
>
> {link}
>
> If you did not request this, you can ignore this email — without your consent
> the account stays locked and we will delete it.
>
> You can withdraw consent at any time from the Family screen in the app, which
> immediately disables the account, and you can ask us to delete their data.

---

## Confirmation email (the "plus" step)

Sent ~24 hours after consent is recorded.

**Subject:** You consented for {child_username} on ScriptureBuddy

> This is a confirmation, not a request.
>
> On {date} we recorded your consent to let **{child_username}** {what} on
> ScriptureBuddy, and their account is now active.
>
> If that was you, there is nothing to do.
>
> If you did **not** give this consent, sign in and open the Family screen to
> withdraw it immediately, or reply to this email and we will disable the
> account and delete their data.
>
> You can withdraw consent at any time.

---

## Scope wording

| Scope | Shown to the parent as |
|---|---|
| `account` | create and use a ScriptureBuddy account |
| `ai_processing` | have AI help check their answers and generate practice questions |
| `social` | add friends and appear on leaderboards |


## Review checklist before launch

- [ ] Reviewed by counsel
- [ ] Links to the full privacy policy (not yet written — M7)
- [ ] Sender address verified in SES and out of the sandbox
- [ ] Reply-to address monitored by the owner
