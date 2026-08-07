# App store submission answers

Prepared answers for the Google Play and Apple App Store questionnaires.
**Nothing here has been submitted.** The plan is friends-and-family testing
first, via the web app and a sideloaded APK, before either store is involved.

Answers are drawn from what the code does. Where an answer depends on something
not yet true, it is marked **BLOCKED**.

---

## The facts both stores will ask about

| Question | Answer |
|---|---|
| Does the app contain ads? | No. There is no ads SDK and no ad network. |
| In-app purchases? | Not at launch. The `entitlements` table exists so this can be added without re-architecting, but nothing is sold today. |
| User-generated content? | **Yes, narrowly.** A display name, 24 characters, and nothing else. No chat, no messaging, no comments, no profile free-text, no avatars, no uploads. |
| Can users interact? | Friends lists and leaderboards only. Users cannot send each other anything. |
| Does the app share location? | No. Never collected. |
| Third-party analytics? | None. |
| Does the app target children? | General audience, used by children with parental involvement. Not submitted to Apple's Kids Category. |
| Account required? | Yes. |
| Can users request deletion? | Yes, in-app, plus the parent-initiated path for a child. |

## Google Play

### Data safety form

**Collected and linked to identity:**

| Type | Collected | Shared | Optional | Purpose |
|---|---|---|---|---|
| Name (display name) | Yes | No | Yes | App functionality |
| Email address | Yes (13+ only) | No | No | Account management |
| User IDs (username) | Yes | No | No | Account management |
| Date of birth | Yes | No | No | App functionality — age-appropriate protections |
| App activity (progress, XP, streaks) | Yes | No | No | App functionality |
| Other (time zone) | Yes | No | No | App functionality — correct day boundary for streaks |

**Not collected:** location, financial info, health, photos, videos, audio,
files, contacts, calendar, SMS, call logs, installed apps, device identifiers
for advertising.

- Data is encrypted in transit: **Yes**
- Users can request data deletion: **Yes**
- Committed to Play Families Policy: **Yes**

Note for the form: for accounts under 13, *email address is not collected at
all*. The table above reflects the maximum across account types, which is what
the form asks for; the distinction should be explained in the policy link.

### Content rating (IARC questionnaire)

- Violence, sexuality, profanity, controlled substances, gambling: **none**
- **Users can interact:** yes — declare it. Friends and leaderboards count as
  interaction even without messaging.
- **Shares user-provided content:** display name only.
- Shares location: no.
- Digital purchases: no.

Expected outcome: **Everyone / PEGI 3**, with an "Users Interact" notice.

### Target audience and content

- Target age groups: include under-13 → triggers **Play Families** requirements
- Families policy: ads-free, no misleading in-app purchase design, COPPA
  compliance attested
- **BLOCKED:** privacy policy URL required. Draft exists at
  `privacy-policy.md`; not hosted.

## Apple App Store

### App privacy ("nutrition label")

**Data linked to you:**
- Contact Info → Email Address (13+ only)
- User Content → Other (display name)
- Identifiers → User ID
- Usage Data → Product Interaction
- Other Data → date of birth, time zone

**Data not collected:** location, contacts, health, financial, browsing history,
search history, sensitive info, diagnostics.

**Tracking:** No. No data is used to track across apps or websites, so no ATT
prompt is required.

### Age rating

- All content descriptors: **None**
- Made for Kids: **No** — general audience with in-app parental controls, the
  approach Duolingo takes. Apple's Kids Category brings stricter rules and, in
  practice, requires an ads/analytics posture we already meet but a review
  process we do not need.
- Expected rating: **4+**

### Review notes to include

> ScriptureBuddy has no chat or messaging of any kind. The only user-generated
> content is a display name of up to 24 characters, which is screened by an
> automated classifier before it is visible to anyone else; names that fail are
> hidden and the account's username is shown instead. Users can block other
> users and report display names. Accounts for children under 13 are created by
> a parent, hold no email address or real name, and cannot be used until the
> parent confirms consent by email.

**Demo account for review:** _(create a dedicated reviewer account — do not give
Apple the owner account, which has admin access)_

## Blockers before either store

1. **Privacy policy hosted at a stable public URL** — both stores require it,
   and it must be reachable without signing in.
2. **Monitored support contact** — required for UGC apps on both stores.
3. **SES configured** — a reviewer testing the child flow would otherwise hit a
   dead end waiting for a consent email.
4. **Apple Developer Program** — $99/yr, not yet purchased. Needed even for
   TestFlight.
5. **Google Play Developer** — $25 one-time, not yet purchased.
6. **Reviewer demo account** with a child account already set up, so the
   parental flow can be inspected without waiting on email.
7. **Account deletion discoverable in-app** — Apple requires an in-app path to
   delete the account, not only a contact form. A parent can delete a child's
   account today; an adult deleting *their own* account is not yet wired up.

## Friends-and-family testing (no store involved)

- **Web:** already live at the CloudFront URL. Nothing to install; works on
  phones. This is the fastest way to get testers going.
- **Android:** `flutter build apk --release` with the three dart-defines, then
  share the APK directly. Testers must allow install from unknown sources.
- **iOS:** not possible without the Apple Developer Program. Direct testers to
  the web app on iPhone.
