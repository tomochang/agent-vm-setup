# Connecting Google services (Drive, Chat)

The personal setup usually starts with mail and calendar. The moment the
work grows — a knowledge base, company-wide information flow — you need
**Drive** (documents) and **Chat** (conversations) as data sources too.
Both are Google Workspace APIs, and both charge the same "connection tax":
nothing works until a Google Cloud project exists and consent is set up.
Budget for it instead of discovering it mid-task.

## The auth model, in one page

There are exactly three ways in, and the order matters:

1. **User authentication (OAuth 2.0, per person).** The agent acts as one
   named person, sees only what that person can see, and the person can
   revoke it at any time. Start here. It matches a read-only,
   results-visible-only-to-the-person phase perfectly.
2. **App authentication (service account).** The agent acts as an
   application. For Chat, the app can only read spaces it is a member of
   (plus a few administrator-approved scopes). Useful later for bot-style
   presence; useless as a first step for reading people's conversations.
3. **Domain-wide delegation (DWD).** An administrator lets a service
   account impersonate users. This is the powerful, dangerous door: it
   needs a Workspace administrator, an audit trail, and a reason.
   Reach for it only when a cross-person feature genuinely cannot work
   any other way, never as a shortcut around consent.

## Shared prerequisites (do once per person)

- A Google Cloud project owned by the person (or the organization).
- The OAuth consent screen configured for that project.
- The API you want enabled in the project (Drive API / Google Chat API).
- An OAuth client of type **Desktop app**; store the downloaded JSON and
  the resulting token in the setup's credentials area (0600, never in a
  repository).

Two traps that bite every first-timer:

- **Testing-mode token expiry.** While the consent screen is in
  "Testing" publishing status, refresh tokens expire in about 7 days.
  The connection then dies weekly and looks like a random failure.
  A setup that must run unattended needs the consent screen published
  (for an organization-internal app this stays inside your domain) or an
  explicit weekly re-consent routine. Decide which on day one.
- **Chat needs an app configuration too.** Unlike most Google APIs,
  the Google Chat API also requires configuring the Chat app (name,
  icon, description) in the Cloud project before calls succeed —
  including calls made with user authentication.

## The two workflows

- [drive.md](drive.md) — read-only Drive connection: scopes, steps,
  verification, and the failure table.
- [chat.md](chat.md) — Chat connection by user authentication, plus a
  premise-check procedure (is Chat enabled, actually used, and what is
  the external-guest policy?) to run *before* designing anything on top
  of Chat.

Rule for both: connect read-only first, prove the read path with a
known item, and only then build work on top of it.
