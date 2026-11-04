# SETUP — the runbook

You are the setting-up agent. Execute the phases in order. Each phase
ends with a **Verify** step: do not move on until it passes, and say
exactly which state you are in (started / running / done) when you
report. Steps marked **[HUMAN]** are the only ones you may stop for;
prepare everything around them so the human's part takes seconds.

Conventions: `$RECORDS` = your private records repo (Phase 1).
Credentials live only in 600-permission files under `~/.config/` or in
gitignored `credentials/` inside `$RECORDS`. Never print a secret value.

## Phase 0 — Environment survey

- Confirm: Linux, persistent home, `git`, `python3`, `node`/`npm`,
  `curl` available. Note what is missing; install with the system
  package manager where possible.
- Check whether your home survives VM replacement. Anything installed
  under `/usr` or `/root` may be wiped on hosted VMs — prefer `$HOME`
  installs (e.g. an npm prefix inside `$HOME`) and plan to re-restore
  the rest from the bootstrap script (Phase 5).
- If the VM reaches the internet through a proxy whose credentials
  rotate per session, find out whether it accepts credential-free
  CONNECT. Long-lived processes (Beeper) must not capture a
  credentialed proxy URL at launch time; it goes stale and fails
  mysteriously (HTTP 407 under a generic error message).

## Phase 1 — Records repo (source of truth)

1. **[HUMAN]** Human signs in to GitHub (passkey) and creates a
   *private* repo, e.g. `records`. (Or creates it and adds you.)
2. Clone it. Create the skeleton:
   `docs/`, `skills/`, `tools/`, `private/` (todo + records),
   `credentials/` (gitignored), `templates/` copied from this repo.
3. Add `.gitignore` entries: `credentials/`, `*.token`, `oauth.json`.
4. Land the first commit through the gate pattern you will use from
   now on: work in a branch/worktree, never commit directly on the
   shared clone's main.
- **Verify**: a trivial change lands and `git pull` on the main clone
  shows it.

## Phase 2 — Builder and reviewer sign-ins

1. Install Claude Code into a persistent prefix
   (`npm config set prefix ~/.npm-global` style) so a VM replacement
   does not remove it.
2. **[HUMAN]** Claude Code OAuth sign-in. Run a trivial prompt inside
   the records repo as a smoke test.
3. Install Codex similarly.
4. **[HUMAN]** Codex device-flow sign-in.
5. Note for later: on some VM images the bundled `codex` binary lacks
   its code-mode host and crashes on tool use. If bare `codex exec`
   dies, run reviews with code mode disabled and the content embedded
   in the prompt, or use the full npm distribution which bundles the
   host. Record which one your VM needs in the records repo.
- **Verify**: both tools answer a trivial prompt.

## Phase 3 — Beeper (the inbox)

1. Download Beeper Desktop (Linux AppImage), extract it
   (`--appimage-extract`) to `~/Applications/squashfs-root` — no FUSE
   needed.
2. Copy `beeper/launch-beeper.sh` to `~/workspace/beeper-diag/` and run
   it. It brings up Xvfb `:99`, a D-Bus session, the accessibility bus,
   openbox, and Beeper with CDP on 9222 and the local API on 23373.
3. **[HUMAN]** Sign in: email code, then SAS emoji verification with
   the phone. Wait for initial sync to finish.
4. Issue the Desktop API token with the canonical script:
   `python3 beeper/oauth_setup.py "read write"` — it registers an
   OAuth client (PKCE), you approve the connection **inside the Beeper
   app** (the agent may drive the clicks via the CDP driver: check
   "Allow sensitive actions", set expiry to **Never** — note the expiry
   control is a native `<select>`; set its value, clicking the option
   text does nothing). Tokens land in `~/.config/beeper/oauth.json`
   (600). Never expires, no refresh token; on `AUTH_EXPIRED`, re-run.
5. If your tooling wants a bare token file, copy `access_token` from
   `oauth.json` into `$RECORDS/credentials/beeper-token` (600).
6. Sending attachments goes through the API, not the UI:
   `POST /v1/assets/upload` (multipart) → `uploadID` →
   `POST /v1/chats/<chatID>/messages` with
   `{"attachment": {"uploadID": ...}}`; send cover text as a separate
   message and verify by reading the thread back.
- **Verify**: `curl -H "Authorization: Bearer <token>"
  http://127.0.0.1:23373/v1/accounts` returns 200 and your accounts;
  a chat search finds a known conversation. Restart Beeper via the
  launch script and confirm the API comes back.

## Phase 4 — healthchecks.io (dead man's switch)

1. Create a free account. The agent-managed route: request the emailed
   login link, read it from the connected mailbox, open it in the
   browser session, and you are in — no password needs inventing.
   **[HUMAN]** only if the account already belongs to the human and
   they want to tap anything themselves.
2. Add a check: cron schedule matching your health loop (e.g.
   `*/30 * * * *`), grace 15 min, email notifications on.
3. Store the ping URL (and a *read-only* API key if you will run a
   judge) in `~/.config/healthchecks/credentials` (600). One warning
   earned in production: rotating the read-only key breaks every other
   consumer of the old key (another agent's judge got a 401). Hand a
   replacement key to another agent only encrypted to a public key
   they generated for that purpose.
4. A judge (optional, for multi-agent setups) polls the API with the
   read-only key every ~15 min and alerts on state changes; keep its
   state file on the VM, not in git.
- **Verify**: test ping returns OK and the API shows the check `up`.

## Phase 5 — Health loop (stays alive by itself)

1. Adapt `health/bootstrap-check.sh.template` to your VM: one line per
   invariant (tool present, config present, Beeper up + API 200…).
   The check only reports; it never fixes.
2. Adapt `health/vm-bootstrap.sh.template`: idempotently restore
   everything a VM replacement wipes (mirrors into volatile paths,
   app relaunches including Beeper, locales, temp dirs). Single
   instance (flock). It is called *by* the loop, never by hand-waving.
3. Schedule a 30-minute job: ping (Phase 4) → check → bootstrap once →
   recheck → surface remaining failures to the human, stay silent
   when all green.
4. Initialize `health/failure_ledger.py` next to its JSONL log; add a
   30-minute check job that stays silent unless an unresolved repeated
   failure exists.
5. Add an auto-pull job (~30 min) for the records repo: `git fetch`
   and `git pull --no-rebase --no-edit` as separate steps; silent
   unless the tree is dirty or a pull conflicts.
- **Verify**: kill Beeper, run one loop iteration, watch the loop
  relaunch it and end green. Simulate a VM wipe of one restored item
  if your platform allows it.

## Phase 6 — Working rules

1. Copy `templates/AGENTS.md` into the records repo root and adapt the
   names. This is the resident rule file; keep it short — rule bodies
   live in skills, selected by situation.
2. If a second agent serves the same human, adopt
   `templates/agent-coordination.md` from day one. It is much cheaper
   than learning it from a duplicated setup.
3. Decide your gates now: which actions always need the human
   (payments, bookings, external sends), and what counts as proof of
   completion (a confirmation email / account record / readback —
   never a work summary).
- **Verify**: the human can state back the approval boundaries in one
  sentence each. If they can't, the rules are too long.

## Done

Report to the human: what is up, what you verified (with the actual
check outputs behind each claim), which human steps remain, and the
one-line status of each phase — started / running / done, exactly.
