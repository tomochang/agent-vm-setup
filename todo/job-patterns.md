# The two todo jobs

Two small scheduled jobs keep the todo honest. Both are *silent
unless something changed* — a job that reports "nothing happened"
trains the human to ignore the one that matters.

These are patterns, not shipped scripts: the preflight/watermark
mechanics (a state file holding the last-seen timestamp or message
ID per source, compared cheaply before any model wakes) are
specified by the steps below, and the implementation is a short
script per deployment.

## 1. Inbox sync — the sensor (~every 30 min)

Reads the messaging inbox and flips todo states on the events found
there. Its whole job is classification on evidence:

1. **Preflight.** A cheap script verdict first: if nothing changed
   since the last run's watermark, exit immediately — no reads, no
   report. The full pass is the exception, not the default.
2. **Read the todo in full** before classifying anything. A snippet
   or a grep is a shallow read, and shallow reads misclassify.
3. **Classify new work** into the state model: executable now →
   `ready`; waiting on a counterparty → `waiting_external`; needs
   the human → `waiting_user` (only when the ball is verifiably
   theirs — if the next step belongs to a counterparty, e.g. choosing
   a venue, it is `waiting_external`); depends on a task or a date →
   `waiting_precondition`.
4. **Detect unblocking events.** For each waiting item, check the new
   messages for what it was waiting on. The human's own outgoing
   messages count as evidence too. On an event: flip to `done` (with
   the evidence), to `ready` (follow-up is agent-doable), or to
   `waiting_user` (the ball moved to the human). Never flip on
   inference; unresolved stays open and is noted in the log.
5. **Land through the gates** (see [../workflows/gates.md](../workflows/gates.md)):
   consistency check on the changed items, then commit.
   Advance the watermark only after successful processing.

Existence checks inside this job follow the hard rule: paginate a
chat to the end before concluding anything is absent.

## 2. Auto-advance — the worker (~every 30 min)

Works the `ready` items. Its defining line is **execute vs.
transition**:

- **Execute** when the item fully determines the action: the specific
  booking/order, dates, parties and price are already decided or
  recorded, and no material choice remains. Refundable, changeable
  actions inside a recorded budget are in scope.
- **Transition** to `waiting_user` — with the options, drafts or
  materials prepared — when any material choice is open: which
  option, a price above the recorded figure or with no figure
  recorded, a non-refundable commitment the item does not explicitly
  direct, or a personal decision (family replies, invitations,
  gifts). Personal decisions are never executed, only prepared.

Operating rules that keep it safe:

- **Claim first** (see [README.md](README.md)): at most 2 items per
  run, nearest hard deadline first. Re-read the landed claim before
  acting; a live claim by another agent means skip.
- **Mandate.** An item whose authorization is only inferred — no
  explicit instruction in the item, its log section, or a linked
  case — may be *prepared* but never executed externally.
- **Recovery journal.** Before any external action, append an
  *intent* line (action, target, unique key) to a local journal;
  after completion append *done* with the evidence. At run start,
  reconcile: an open intent is an *unknown outcome* — verify it in
  the real system before repeating anything.
- **Report discipline.** Always report an executed reservation,
  payment or order (what, amount, confirmation). Report completions
  and items that newly became `waiting_user`. Nothing else — no
  play-by-play.
