# SETUP — the runbook

You are the setting-up agent. Execute the phases in order. Each phase
ends with a **Verify** step: do not move on until it passes, and say
exactly which state you are in (started / running / done) when you
report. Steps marked **[HUMAN]** are the only ones you may stop for;
prepare everything around them so the human's part takes seconds.

Conventions: `$RECORDS` = your private records repo (Phase 1).
Credentials live only in 600-permission files under `~/.config/` or in
gitignored `credentials/` inside `$RECORDS`. Never print a secret value.

**Owner start**: the human begins by pasting the prompt in
`KICKOFF.md` to you. If you are reading this without having received
it, ask for it once — it carries standing instructions (posture,
reporting, persistence) that the phases below assume.

## Profiles — read this first

The full shape below serves an operator running several agents and
machines. A first-time, single-agent adopter runs the **minimal**
profile instead — a dual review of this package against a real
beginner adopter found the full shape stalls them between Phases 1
and 3:

- **minimal**: Phases 0, 1-local, 3, 4 (author-hosted option), 5, 6,
  then Phase 8 (the flagship). Phases 2 and 7 wait until a real need
  appears. The owner's own time is roughly 75–120 minutes across
  3–4 sittings, most of it one live sitting with the author present
  (Phase 3).
- **full**: all phases in order. The cover estimate (30–60 minutes)
  assumes this profile's sign-ins go smoothly with the owner at a
  laptop.

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
  the rest from the bootstrap script (Phase 5). The survival model
  behind this — what dies, what the bootstrap must restore, and the
  drill that proves it — is `durability/RESTART-SURVIVAL.md`; read
  it before Phase 5.
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

**Minimal profile — Phase 1-local instead.** Skip GitHub for now:
`git init` the records repo inside `$HOME` with the same skeleton
and `.gitignore`, and schedule a nightly archive of it to the
owner's cloud drive (most agent platforms already have a drive
connector, and a beginner owner is usually already signed in to
it). Version history and off-machine backup are weaker than a
hosted repo — accept that trade consciously, and graduate to the
hosted form when a second machine or agent appears. What must NOT
be weakened: the skeleton, the gitignore, and the branch
discipline.

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
   over chat, and type back the code they return under *Credential
   and code hand-over* below. Wait for initial sync to finish.
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
7. Link the owner's messaging account(s) in Beeper (e.g. WhatsApp):
   in Beeper's settings, add the account and complete its link flow.
   The link needs a QR code shown on a screen the owner's phone can
   scan — which the phone itself cannot be — or a pairing code, so
   schedule this inside the live sitting with a second screen at
   hand. Verify by exchanging a real message in the support channel.
- **Verify**: `curl -H "Authorization: Bearer <token>"
  http://127.0.0.1:23373/v1/accounts` returns 200 and your accounts;
  a chat search finds a known conversation. Restart Beeper — kill it
  first with the bracket form `pkill -f '[b]eepertexts'` (a plain
  pattern matches your own shell's command line and kills it), then
  run the launch script — and confirm the API comes back. The
  launcher alone exits 0 without restarting when Beeper is already
  running.

### Credential and code hand-over (all phases)

Rules elsewhere in this package say "no credentials in chat, ever".
Read literally, that makes several required steps impossible — the
owner's only channel to the agent IS chat. The actual rule:

- Never in a group or supervisor channel. Never to another agent.
  Never in the records repo or any file that syncs.
- To the owner's own agent, in their private 1:1 chat, an item may
  pass only when the agent has asked for that specific item (an API
  password, a one-time code with no direct-entry route). The agent
  writes it straight to a 600-permission file or its credential
  store, confirms receipt by key name only (never echoing the
  value), and the owner deletes the message afterwards.
- Prefer routes where the owner types the secret into the service's
  own screen (secure entry forms, pairing codes) whenever one
  exists; the chat route is the fallback, not the default.
- Time-limited flows (QR codes, timed consents, expiring links) are
  opened only while the owner is present in a scheduled sitting —
  never asynchronously, or the agent will re-ask and spam.

## Phase 4 — healthchecks.io (dead man's switch)

1. Create a free account, registered to an email address the agent
   can read (or the human's own, if they prefer). The agent-managed
   route: request the emailed login link, read it from the connected
   mailbox, open it in the browser session, and you are in — no
   password needs inventing. (This assumes your platform gives you a
   mailbox you can read and a browser session — givens for the agent
   platform this package targets.) **[HUMAN]** only if the account already
   belongs to the human and they want to tap anything themselves.
   (Minimal profile: the author may host the check in their own
   healthchecks account and hand over only the ping URL — the alerts
   then land where the support actually happens.)
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
   app relaunches including Beeper, system tools installed outside
   `$HOME` — language runtimes and CLIs your gates depend on —
   reinstalled service units, locales, temp dirs). Single
   instance (flock). It is called *by* the loop, never by hand-waving.
   Every tool any earlier phase installed outside `$HOME` goes on the
   bootstrap's restore list in the same change; an install that is
   not on the list is scheduled amnesia
   (`durability/RESTART-SURVIVAL.md`).
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
6. Register a **boot trigger**: the same health-loop script, run once
   at startup. systemd: adapt `health/agent-boot.service.template`
   (its unit file is kept in `$HOME` and reinstalled by the bootstrap
   like every other restore-list item); cron: an `@reboot` line;
   platform jobs: a startup-triggered job if one is offered. The
   30-minute cadence alone leaves a rebooted VM unrestored until the
   first tick — in field use, a morning reboot went unrepaired for
   hours because nothing ran the loop at boot.
- **Verify**: kill Beeper, run one loop iteration, watch the loop
  relaunch it and end green. Then run the **restore spot-check**:
  delete one restored item per class (a unit file, a package, a
  mirror) and let one loop cycle restore it. The full restart drill
  runs at the very end (see *Final verification*) — asked earlier,
  it would demand proof of things Phases 6–8 have not installed yet.

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
- **Verify**: the agent posts the approval boundaries in the owner's
  language, one sentence each, and the owner confirms or corrects
  them. If the agent cannot state them that plainly, the rules are
  too long.

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
3. **Skills + tools full set.** `skills/` ships 45 generalized
   procedures and `tools/` ships the operator tools (coverage
   checks, watchers, spend governor, receipt library). Copy the
   ones you need into the records repo's tooling and set the path
   env vars noted in `tools/README.md`.
4. **Workflows.** Adopt as needed: watchers
   (`workflows/watchers.md`) for every chat where a counterpart's
   reply matters — registered in the health loop's coverage check in
   the same step; the gates flow (`workflows/gates.md`) for all
   records landings; the handoff protocol (`workflows/handoff.md`)
   if a second machine does heavy work; the improvement loop
   (`workflows/improvement-loop.md`) once the rest is stable.
- **Verify**: add a todo item, watch one sync cycle classify an
  inbox message into it, and land one change of each kind (a todo
  flip, a doc) through the gates.

## Phase 8 — The flagship task

The setup exists to serve the owner's real work. For an adopter
whose purpose is one clear task (an athlete's performance data, a
shop's books), that task is a phase, not an afterthought:

1. Before the live sitting, the author side establishes whether the
   owner's issued account can use the data source's API at all, and
   what its terms allow (automated access, storing the data,
   sharing it). If that needs the issuing organisation's
   administrator, ask early — the answer can take days. Test
   read-only endpoints, a handful of attempts, never a retry loop
   against someone else's account system.
2. In the sitting: the owner enters the credentials on their own
   side (see *Credential and code hand-over*); the agent installs
   the client and runs the smallest real query.
3. The agent produces ONE small real output from the owner's data
   and reviews it with the owner in their language — sanity-checking
   units, labels and known values against what the owner already
   knows.
4. If API access is refused or absent, fall back the same week:
   export (e.g. CSV) from the service's own UI into the owner's
   drive, and analyse that. "Your account cannot use the API" must
   never be the setup's only visible outcome.
- **Verify**: the owner has seen one real output and confirmed it
  matches their data.

## Final verification (after Phase 6, and Phases 7–8 where taken)

Run the full **restart drill** (`durability/RESTART-SURVIVAL.md`)
only now: restart the VM — or delete one restored item per class —
hands off, let one loop cycle restore everything, confirm the boot
trigger fired (the restore already in progress or done before the
first scheduled tick). Two scope notes:

- A reboot proves the boot trigger and the restore list. A VM
  *replacement* additionally proves the job registrations
  themselves survived; record which of the two you actually tested.
- The owner's part is small and in their language: the agent posts
  its approval boundaries and supervisor arrangements as a short
  plain-language summary (about three sentences), and the owner
  replies yes or corrects it. Do not ask a beginner to recite rules
  back from memory.

## Guided onboarding (when the adopter is a beginner)

A runbook alone assumes an operator who already thinks this way. If
the human adopting this setup is a beginner, treat the first week as
guided, not self-serve:

- Keep the support channel warm: expect questions, and answer with a
  worked example from a real (sanitized) case, not just a rule.
- Review the first real outputs together as they appear — the first
  morning triage, the first evening wrap-up, the first meeting brief —
  and correct course in the channel, the same day.
- Expect the new agent to be over-cautious (asking before building)
  or, occasionally, over-bold; the envelope in OPERATOR.md and rule 8
  of the AGENTS core are the calibration, and the guide's job is to
  point at them in context until the agent applies them unprompted.
- Step guidance down to on-request only after outputs pass review
  several days running.

## Done

Report to the human: what is up, what you verified (with the actual
check outputs behind each claim), which human steps remain, and the
one-line status of each phase — started / running / done, exactly.
Where the adopter has a flagship task, "done" also requires its
first real output to have been shown to the owner (Phase 8) and the
final verification above to have passed.

**Operating posture from day one**: you are in a value-proving phase.
Under the AGENTS.md core rules (rule 8), build and show reversible
local work without waiting for approval; the approval gate sits at
external or irreversible actions only. Do not let a new principal's
first experience of you be a queue of permission requests.
