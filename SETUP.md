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

- These VMs are single-tenant agent boxes: the setup and the health
  loop run as root (or with sudo throughout), and `$HOME` below is the
  agent user's home. State which user you are before Phase 1.
- Clone this repo somewhere stable, e.g. `~/workspace/agent-vm-setup`;
  later phases reference its files by relative path from there.
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
2. Give the VM its own access — a repo-scoped **deploy key**, not the
   human's login: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519`, then
   **[HUMAN]** pastes the *public* key into the repo's Settings →
   Deploy keys (write access on). Add an `~/.ssh/config` host block
   for `github.com` (if your egress needs the port-443 endpoint, use
   `HostName ssh.github.com`, `Port 443`). The `gh` CLI is optional;
   if you install it, **[HUMAN]** runs its device-flow login once so
   `~/.config/gh/hosts.yml` exists under `$HOME` (not a volatile
   path).
3. Clone it. Create the skeleton:
   `docs/`, `skills/`, `tools/`, `private/` (todo + records),
   `credentials/` (gitignored), `templates/` copied from this repo.
4. Add `.gitignore` entries: `credentials/`, `*-credentials`,
   `*.token`, `oauth.json`, `.env`.
5. Commit the skeleton on a branch/worktree, never directly on the
   shared clone's main. The full landing gates are decided in
   Phase 6; until then, branch + the human's glance is enough — do
   not invent extra approval stops.
- **Verify**: a trivial change lands and `git pull` on the main clone
  shows it.

## Phase 2 — Builder and reviewer sign-ins

1. Install Claude Code into a persistent prefix so a VM replacement
   does not remove it: `npm config set prefix ~/.npm-global`, add
   `~/.npm-global/bin` to PATH (in `~/.bashrc` — checks that call
   `command -v` fail without it), then
   `npm install -g @anthropic-ai/claude-code`. Claude Code and Codex
   need Node 20+; if the distro's `nodejs` is older, install a
   current Node first (vendor tarball into `$HOME`, or NodeSource) —
   do not let Phase 0's package manager strand you on an old one.
2. **[HUMAN]** Claude Code OAuth sign-in. Run a trivial prompt inside
   the records repo as a smoke test.
3. Install Codex similarly: `npm install -g @openai/codex`.
4. **[HUMAN]** Codex device-flow sign-in.
5. Note for later: on some VM images the bundled `codex` binary lacks
   its code-mode host and crashes on tool use. If bare `codex exec`
   dies, run reviews with code mode disabled and the content embedded
   in the prompt, or use the full npm distribution which bundles the
   host. Record which one your VM needs in the records repo.
- **Verify**: both tools answer a trivial prompt.

## Phase 3 — Beeper (the inbox)

1. Install the headless-desktop dependencies first (a clean Ubuntu
   has none of them): `apt-get install -y xvfb openbox at-spi2-core
   libglib2.0-bin libgtk-3-0 libnss3 libasound2 libgbm1 libxss1`.
   Download Beeper Desktop (Linux AppImage) from beeper.com/download,
   `chmod +x` it, then `cd ~/Applications` and extract it there
   (`--appimage-extract` writes `squashfs-root` into the *current*
   directory) — no FUSE needed.
2. Copy the whole `beeper/` directory to `~/workspace/beeper-diag/`
   (the liveness script imports its sibling `beeper_api.py` and calls
   its sibling launcher) and run `launch-beeper.sh`. It brings up
   Xvfb `:99`, a D-Bus session, the accessibility bus, openbox, and
   Beeper with CDP on 9222 and the local API on 23373. If 23373 does
   not answer once the app is up, enable the Desktop API in Beeper's
   settings and relaunch.
3. **[HUMAN]** Sign in — but the human never sees this VM's display:
   Beeper runs on headless Xvfb. You drive the sign-in screen via
   `beeper/cdp.py`, so install its dependency *first*:
   `python3 -m pip install --target ~/.pylibs websocket-client`
   (if `python3 -m pip` itself is missing: `apt-get install -y
   python3-pip`; on PEP 668 systems the `--target` form is the one
   that works). Then, via `cdp.py`: read the email-code field state
   and the SAS emoji sequence out of the DOM, relay them to the human
   over chat, and type the code they give you back. Wait for initial
   sync to finish.
4. Issue the Desktop API token with the canonical script:
   `python3 beeper/oauth_setup.py "read write"`. It prints an
   `AUTH_URL` and waits for a redirect to a local callback — open the
   URL **inside the Beeper renderer** via `cdp.py` (assign
   `location.href`); the consent screen renders in the app itself.
   The clicks are yours (the agent's), driven by `cdp.py`.
   On the consent screen: check "Allow sensitive actions", and set
   expiry to **Never** — the expiry control is a native `<select>`;
   find the option whose text is "Never", assign that option's value
   to `select.value`, and dispatch a `change` event (clicking the
   option text does nothing, and a silent 30-day default is the
   classic failure). Tokens land in `~/.config/beeper/oauth.json`
   (600). Never expires, no refresh token; on `AUTH_EXPIRED`, re-run.
5. `oauth.json` is the canonical token store. The bootstrap-check
   template also wants a bare token file: copy `access_token` from
   `oauth.json` into `$RECORDS/credentials/beeper-token` (600) — a
   derived copy; refresh it whenever you re-issue the token.
6. Sending attachments goes through the API, not the UI:
   `POST /v1/assets/upload` (multipart) → `uploadID` →
   `POST /v1/chats/<chatID>/messages` with
   `{"attachment": {"uploadID": ...}}`; send cover text as a separate
   message and verify by reading the thread back.
- **Verify**: `curl -H "Authorization: Bearer <token>"
  http://127.0.0.1:23373/v1/accounts` returns 200 and your accounts;
  a chat search finds a known conversation. Restart Beeper — kill it
  first with the bracket form `pkill -f '[b]eepertexts'` (a plain
  pattern matches your own shell's command line and kills it), then
  run the launch script — and confirm the API comes back. The
  launcher alone exits 0 without restarting when Beeper is already
  running.

## Phase 4 — healthchecks.io (dead man's switch)

1. Create a free account, registered to an email address the agent
   can read (or the human's own, if they prefer). The agent-managed
   route: request the emailed login link, read it from the connected
   mailbox, open it in the browser session, and you are in — no
   password needs inventing. (This assumes your platform gives you a
   mailbox you can read and a browser session — givens for the agent
   platform this package targets.) **[HUMAN]** only if the account already
   belongs to the human and they want to tap anything themselves.
2. Add a check: cron schedule matching your health loop (e.g.
   `*/30 * * * *`), grace 15 min, email notifications on.
3. Store the ping URL **and a read-only API key** in
   `~/.config/healthchecks/credentials` (600), one `key=value` per
   line: `ping_url=...`, `api_key_readonly=...`. The key is not optional
   decoration — the Verify step below and any judge read through it. One warning
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
3. Schedule a 30-minute job running `health/health-loop.sh.template`
   (adapted): ping (Phase 4) → check → bootstrap once → recheck →
   surface remaining failures to the human, stay silent when all
   green. Run the loop as the same user that owns the records repo
   and `$HOME`, and pin HOME/PATH in the job definition rather than
   relying on sudo's environment. The channel it surfaces on is your
   normal chat with the human — on an agent platform the job's
   non-empty output is the message (on plain cron, pipe it to your
   own notifier; cron mail is not a chat).
4. Initialize `health/failure_ledger.py` next to its JSONL log; add a
   30-minute check job that runs its `check` and surfaces the output
   only when it exits non-zero (`ok: false`) — the JSON it prints on
   success is for the job to consume, not to forward.
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

## Phase 7 — The working systems (todo, skills, workflows)

1. **Todo.** Copy `todo/` into the records repo's tooling. Create
   `private/todo.md` (with the state-model header from
   `todo/README.md`), `private/todo_done.md` and `private/todo_log.md`.
   Adopt the 3-line format (`todo/todo-format.md`) for new items and
   run `todo/todo_consistency.py check --base origin/main` before any
   landing that touches the file. Schedule the two jobs from
   `todo/job-patterns.md` (~30 min each): inbox sync, then
   auto-advance.
2. **Skills.** Create `skills/` in the records repo. Move any
   procedure longer than a few lines out of the resident file into a
   `SKILL.md` (see `skills/README.md` for the format and authoring
   rules) and put the *situation → skill* row for it in the resident
   file's map. Start with the procedures you already repeat.
4. **Skills + tools full set.** `skills/` ships 45 generalized
   procedures and `tools/` ships the operator tools (coverage
   checks, watchers, spend governor, receipt library). Copy the
   ones you need into the records repo's tooling and set the path
   env vars noted in `tools/README.md`.
3. **Workflows.** Adopt as needed: watchers
   (`workflows/watchers.md`) for every chat where a counterpart's
   reply matters — registered in the health loop's coverage check in
   the same step; the gates flow (`workflows/gates.md`) for all
   records landings; the handoff protocol (`workflows/handoff.md`)
   if a second machine does heavy work; the improvement loop
   (`workflows/improvement-loop.md`) once the rest is stable.
- **Verify**: add a todo item, watch one sync cycle classify an
  inbox message into it, and land one change of each kind (a todo
  flip, a doc) through the gates.

## Done

Report to the human: what is up, what you verified (with the actual
check outputs behind each claim), which human steps remain, and the
one-line status of each phase — started / running / done, exactly.
