# Restart survival — why agents "go silent", and the mechanism that prevents it

## The failure

Hosted agent VMs get replaced: redeploys, host maintenance, platform
upgrades. A replacement keeps the home directory and wipes everything
else. The agent wakes up on a fresh machine that happens to contain
its files.

From the outside, what follows looks like a behavior problem: the
agent stops replying, or replies but has quietly reverted to factory
caution — gating everything behind approvals it was told not to gate,
ignoring standing instructions it had adopted. It is not a behavior
problem. It is amnesia with specific, predictable contents:

| Lives in the home directory — survives | Lives anywhere else — wiped |
|---|---|
| Records repo, rules files, skills | System packages (`/usr`): language runtimes, CLI tools installed by the package manager |
| Credential stores under `~/.config`, gitignored `credentials/` | Anything under `/root` (configs tools read when run as root) |
| Watcher state, cron/job definitions the platform persists | systemd units in `/etc/systemd/system` |
| Templates and scripts kept in the repo | Running processes: desktop apps (Beeper), watchers, local servers |
| The bootstrap script itself | Package caches and indexes (the first reinstall is also the slowest) |

Every row on the right is a way for a set-up agent to come back
wrong: a records gate that fails because its language runtime is
gone; a CLI that lost its login because the config mirror vanished;
an inbox nobody is watching because the watcher process died and its
unit file went with the machine.

## The three mechanisms

**1. Originals live in the home directory; volatile paths get mirrors.**
Never let the only copy of anything sit in a wiped location. Where a
tool insists on reading a volatile path (`/root/.config/...` when run
as root), bootstrap copies the home original there — the copy is
disposable by design.

**2. The bootstrap restore list is declared, not remembered.**
`health/vm-bootstrap.sh.template` restores, idempotently: config
mirrors, relaunched apps, reinstalled service units, and **system
tools**. The discipline that makes this work: *whenever any phase of
the setup — or any later work — installs something outside the home
directory, adding it to the bootstrap's restore list is part of the
same change.* An install that is not on the list is scheduled
amnesia. The list is short and explicit: a command name and how to
put it back.

**3. Detection does not depend on the agent noticing.**
The health loop (SETUP Phase 5) runs every ~30 minutes whether or
not a replacement happened: ping the dead man's switch → run
bootstrap-check (one line per invariant, including one per restore-
list tool) → run bootstrap once if anything failed → recheck →
surface what is still broken to the human, stay silent when green.
Worst case, a replacement costs one loop interval of degraded
service — not a day of unexplained silence. The dead man's switch
covers the worse case where the loop itself never comes back.

**Close the boot gap.** A 30-minute loop still leaves a rebooted VM
unrestored until the first tick, and a reboot just after a tick
leaves nearly a full interval. Register the same loop script as a
boot job (a oneshot service, an `@reboot` cron line, or a platform
startup job) so recovery starts at boot. After a full VM
*replacement* the boot job's own registration may be wiped too; the
loop and the dead man's switch backstop that case, and the bootstrap
reinstalls the boot job like everything else on the restore list.

## The restart drill (required before "setup done")

A setup that has never survived a restart is unproven in exactly the
dimension that will fail first. Before reporting the setup complete:

1. Restart the VM (or, where the platform forbids it, delete one
   restored item per class: one restore-list tool, one config
   mirror, one service unit, and kill the inbox app).
2. Do not repair anything by hand. Let one health-loop cycle run.
3. Prove, with check output: bootstrap-check is green; the inbox app
   answers its API and returns chats; watchers are running; scheduled
   jobs are registered; and the boot trigger's run is visible in the
   log before the first scheduled tick would have fired.
4. Prove the agent came back *as itself*: ask it in its channel to
   state its approval boundaries and, if it has them, its supervisor
   arrangements. The correct text means its rules files loaded; a
   generic answer means something on the right-hand side of the
   table is still load-bearing.

Log the drill in the failure ledger as a resolved signature
(`vm-replacement-amnesia`) with the drill date, so the next real
replacement is measured against it.

## Field notes

- The expensive version of this failure is not the wipe; it is the
  hours spent diagnosing a "misbehaving" agent whose tools were
  simply gone. When an agent suddenly goes quiet or cautious after
  any infrastructure event, check the restore list first, behavior
  second.
- An application can be up and useless: process alive, API
  answering, account signed out, inbox empty. A check that stops at
  "API 200" certifies a corpse. Every app invariant must end at data
  actually flowing — a list call that returns real items (the
  bootstrap-check template's Beeper lines show the shape).
- Package mirrors can be the bottleneck of a restore: a full package
  index refresh on a slow mirror has taken ~10 minutes while a
  single fast mirror finished in well under one. If your platform's
  default mirror is slow, pin the bootstrap's package step to the
  fastest mirror your platform offers.
- Install under the home directory whenever the tool allows it
  (inside-home package prefixes, user-level installs). Every tool
  that lives in the home is a tool the bootstrap never has to
  restore.
