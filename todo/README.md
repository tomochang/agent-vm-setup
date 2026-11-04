# The todo system — one state file, flipped by events

The setup's task memory is a **single markdown file in the records
repo** (`private/todo.md`), shared by the human and every agent.
There is no separate human list and agent queue — two state surfaces
for the same work is how items get lost. Three files, three jobs:

| File | Holds |
|---|---|
| `todo.md` | Current state only: open items in the 3-line format ([todo-format.md](todo-format.md)) |
| `todo_done.md` | Completions, moved out of `todo.md` with their evidence |
| `todo_log.md` | Progress and evidence, appended as dated lines under each item's section |

## The state model

Every item carries a **state** that says *what is blocking it*, and an
**owner** who holds the next step. States flip **on events** — a
reply arriving, a document landing, a date passing — never on a
clock.

| State | Meaning |
|---|---|
| `ready` | Nothing outstanding; an agent can start now |
| `waiting_external` | Blocked on a counterparty (reply / document / acceptance) |
| `waiting_user` | Blocked on the human (decision / input / physical action) |
| `waiting_precondition` | Blocked on another task or a future date |
| `in_progress` | Claimed and being worked |
| `done` | Finished, with evidence — lives in `todo_done.md`, not in `todo.md` |

The owner field names *who acts next*, never a fixed domain: any
agent may take any item. Owners are listed in a small registry in the
file header (name + surface only).

## Claim before work, dispatch before effect

Two records keep multiple agents from colliding:

- **Claim.** Before working an item, flip its state to `in_progress`
  and note the claim (owner, start time, ~30 min expiry) in its state
  line, land that change, and re-read the landed file to confirm
  your claim is the live one. An expired claim may be reclaimed.
- **Dispatch.** Before any outward effect (a send, a payment, a
  booking, an order to an external executor), record the dispatch in
  the item — what, when, and an idempotency key
  (`<item-ref>:<operation>`) — in the same land or one before it.
  Before repeating an action whose outcome is unknown, re-check the
  real system first; never blind-retry.

## Two jobs run it

Detailed patterns in [job-patterns.md](job-patterns.md):

- **Inbox sync** (the sensor, ~30 min): reads the messaging inbox and
  flips states on the events it finds — a counterparty's reply is the
  evidence that unblocks an item. Reports only when something
  changed.
- **Auto-advance** (the worker, ~30 min): claims up to 2 `ready`
  items per run and executes what they fully determine. Anything with
  a material choice left is *transitioned* to `waiting_user` with the
  options or drafts prepared — prepared, never decided.

## Verify before surfacing

A todo entry's own text never settles its outcome. Before flipping an
item to `done`, or telling the human something is missing, settle it
against the primary sources: the full chat history (paginated to the
end — the newest page is not evidence of absence), the calendar, and
the mail confirmations. Unresolved after all three stays *unverified*
and stays open. When an item becomes `waiting_user`, the report to
the human carries a recommendation plus at most 3 lines of rationale,
so the decision is a quick OK/NG.

## The format is enforced, not hoped for

[todo_consistency.py](todo_consistency.py) checks the 3-line format
of added or changed items against a git base revision, so old items
don't block new work and new drift is caught at landing time. Run it
before every land that touches `todo.md`.
