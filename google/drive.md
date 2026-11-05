# Connect Google Drive (read-only, user authentication)

Goal state: the agent can read every Drive file the connected person can
see — list, search, and download/export — proven against a known file.
This is a **cooperative** procedure: the agent prepares and verifies
everything; a human does the handful of steps that must be a human
(creating the Cloud project under the organization, consent-screen
settings, the OAuth consent click, any admin allow-listing).

## Route decision (make this first, it decides the friction)

- **Project inside the organization + consent screen type "Internal"**
  (recommended for a company Workspace): no external verification, no
  7-day testing-token expiry, and the app is trusted inside the domain.
  Needs: the person (or an admin) able to create a project under the
  organization.
- **Personal project**: works, but expect two frictions — the
  organization's API controls may block an outside app's access to
  company data, and a "Testing" consent screen kills refresh tokens
  after about 7 days. Use only for a personal account.

## Steps

Markers: [AGENT] the agent does it. [HUMAN] a person does it; the agent
prepares the exact screen, values, and wording in advance so the human's
part takes minutes.

1. [HUMAN] Create (or designate) a Google Cloud project under the
   organization. If project creation is restricted, this becomes an
   admin request — the agent drafts it.
2. [AGENT] Enable the **Google Drive API** in the project (console link
   and click path prepared for the human if the agent has no console
   access).
3. [HUMAN] Configure the OAuth consent screen: type **Internal**, app
   name, support email. (Internal removes the testing-expiry trap.)
4. [AGENT] Create an OAuth client of type **Desktop app**; download the
   client JSON into the setup's credentials area (0600, git-ignored,
   never committed).
5. [AGENT] Run the authorization flow requesting exactly one scope:
   `https://www.googleapis.com/auth/drive.readonly`
   [HUMAN] Sign in as the person being connected and grant consent.
6. [AGENT] Store the refresh token next to the client JSON (0600).
   Record, in the setup's records: whose account, which project, scope,
   date connected. No token values in records or chat, ever.

## Verification (all [AGENT]; do not skip)

1. `about.get` — returns the connected person's identity. Wrong person
   means wrong account: stop and redo step 5.
2. `files.list` for a **known file** the human names (name, owner,
   modified time must match what the human sees in their Drive UI).
3. Download one small file, and export one Google-native document
   (Docs → plain text or PDF). Both must succeed; export is the path
   most document work depends on.
4. **File-type census** (this doubles as the Drive state survey):
   aggregate `files.list` by `mimeType` over the connected scope and
   report the shares — Google-native docs vs. Office files vs. PDFs,
   and how many PDFs are scans (no extractable text on a sampled few).
   A knowledge-base design that assumes searchable documents dies on a
   scan-heavy Drive; measure it now, while connecting, for free.

## Failure table

- **Refresh token dies after ~7 days** → consent screen is in Testing
  status (external/personal route). Fix: Internal type, or publish the
  consent screen, or schedule a weekly re-consent — decide once.
- **"App blocked" / access denied by administrator** → the
  organization's API controls do not trust the app. Fix is an admin
  action (trust the app's OAuth client ID); the agent drafts the
  request with the client ID and the business reason.
- **403 insufficient scopes** → token was granted for a different scope
  set. Re-run step 5; consent does not merge scopes after the fact.
- **Files visible in the UI are missing from the API** → they belong to
  a shared drive or a different owner than the connected account.
  Connect the right person, or note the scope limit in the records —
  never silently treat a partial view as the whole.

## After it works

Wire the read path into the health check (one `about.get` per run;
failure surfaces as "Drive connection down", not as mysteriously empty
search results). Any later widening — write scopes, more people, shared
drives — is a new decision with its own approval, not a silent upgrade.
