# Connect Google Chat (premise check first, then user authentication)

Chat is the one source you must **not** connect on faith. A design that
assumes "the company talks on Chat" fails if Chat is merely enabled but
unused, or if the real conversations live elsewhere. So this workflow
has two stages: prove the premise, then connect.

## Stage 1 — Premise check (before any connection work)

Answer these with evidence, in this order:

1. **Is Chat enabled, and for whom?** [HUMAN/admin] Admin console shows
   the service status per organizational unit. Without an administrator
   this stays unknown — record it as unknown, not as "probably on".
2. **Is it actually used?** Evidence an agent can find without any
   connection: Chat notification emails in the person's mailbox, spaces
   the person can name, calendar invites with Chat links. Sample a few
   people; "enabled" is not "used".
3. **External guests**: can spaces include people outside the company,
   and do client conversations happen in Chat or by email? [HUMAN/admin]
   The guest policy is an admin setting; the usage reality is a people
   question. Both decide whether client work is even reachable here.

Write the three answers into the records with their evidence. A "no" or
"unknown" is a valid result — it reroutes the design to email and Drive
instead of sinking weeks into an empty source.

## Stage 2 — Connect by user authentication

Prerequisites are the shared ones in [README.md](README.md), plus the
Chat-specific trap: in the Cloud project you must also **configure the
Chat app** (name, icon, description) and enable the **Google Chat API**,
or calls fail even with perfect OAuth.

1. [AGENT] Scopes, read-only, exactly these:
   `https://www.googleapis.com/auth/chat.spaces.readonly`
   `https://www.googleapis.com/auth/chat.messages.readonly`
2. [HUMAN] Consent as the person being connected (same flow as Drive).
3. [AGENT] Verification:
   - `spaces.list` — the spaces returned must match spaces the person
     sees in their Chat UI (spot-check three names with the human).
   - Read the messages of one known space and find a message the human
     names. If the known message is not returned, stop: likely a
     membership or scope problem, not an empty space.

## Hard limits of user authentication (design around them)

- The agent sees **only spaces the connected person is a member of** —
  including their direct messages. There is no "whole company" view;
  company-wide coverage is the sum of per-person connections, each with
  that person's consent.
- App authentication (service account) sees only spaces the app itself
  has joined. Reading arbitrary history as an app requires domain-wide
  delegation with impersonation of a member — an administrator-gated
  later step (see [README.md](README.md)), never the starting point.
- Deleted and edited messages have API-visible states that differ from
  the UI. Any extraction built on Chat must define how it treats them —
  at design time, not after the first wrong summary.

## After it works

Same rule as Drive: one cheap probe (a `spaces.list` count) in the
health check, and re-consent as a new decision whenever the scope of
people or spaces widens.
