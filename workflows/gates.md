# Gates — how a change lands in the records repo

The records repo is the single source of truth, so writing to it is
the one operation that is never casual. Every change — a todo flip,
a new procedure doc, a tool fix — lands the same way:

1. **Fetch, then branch.** Update the local clone, then create a
   worktree on a fresh branch off the latest shared main
   (`wt/<task>-<date>`). Never edit the shared clone's checkout, and
   never use autostash-style shortcuts to get around a dirty tree.
2. **Edit only inside the worktree.** Small commits, each saying what
   it intends. Add files and commit as separate steps.
3. **Run the checks that own the change.** The todo format checker
   for todo edits; the test suite (with a fresh-evidence marker) for
   code changes; a review pass for anything that gates sending,
   payment, or deletion.
4. **Rebase onto the latest main**, then land through the gate
   script — never a plain push to main. The gate re-runs the checks
   against the exact tree being landed.
5. **Clean up.** Pull the main clone, remove the worktree and branch.

The gate script itself is yours to write — deliberately a pattern,
not a shipped binary, because the checks differ per repo. It is a
thin wrapper (tens of lines) that must guarantee exactly three
things: the checks for the change's class run against the rebased
tree (not the author's older checkout), the merge to main happens
only when they pass, and the run leaves a record (a log line or a PR
check) that a later reader can audit. Everything else about it is
taste.

## Why this shape

- **Conflicts surface before they land**, on the branch, not on the
  shared record two agents are both reading.
- **Every fact has one landing.** A booking, a decision, a
  completion is mirrored into the records repo *in the same work
  block* that produced it — "I'll write it up later" is how records
  and reality drift apart.
- **Procedure docs land with the mechanism.** A new tool or workflow
  is not done until its reproduction-grade doc (packages, commands,
  verification, caveats) is in the repo's docs — checked mechanically
  by the coverage checks in the health loop.

## Approval boundaries

The gate flow is for records. Actions in the world — sends,
payments, bookings, deletions in other systems — follow the human's
approval rules (see `templates/AGENTS.md`): inside the recorded
envelope they proceed; outside it, they stop for the human.
