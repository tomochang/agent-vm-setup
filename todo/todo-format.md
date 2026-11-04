# The 3-line todo format

Every open item is **exactly 3 lines**. The format exists because a
free-form list fails in specific, expensive ways: one item once grew
to a single line of ~4,700 characters with nine appended updates —
sub-tasks buried inside it were missed, and a reader (human or model)
could no longer tell its current state. Current state is overwritten
in place; history lives in the log file, never appended to the item.

```markdown
- [ ] **Book the venue deposit for the offsite** <!-- ref: at-20261104-01 -->
  期限: 2026-11-20 hard｜状態: waiting_external｜担当: agent-a｜待ち: venue's invoice｜確認: 2026-11-04
  経緯 → [contract](cases/offsite.md), chat 2026-11-03 (invoice requested)
```

## Line 1 — the next action

- One physical, visible next action, phrased so it ends in a verb.
  "Check" or "consider" alone is not an action — say *what* gets
  opened, sent, or decided, and by what channel.
- The project keeps only its nearest next action here; later steps
  are created when they become nearest.
- An optional stable reference (`<!-- ref: ... -->`) keeps
  cross-references working when the title is edited.

## Line 2 — deadline, state, owner, last-checked

Fields separated by `｜`, always in this order:

- `期限:` (deadline) — a date plus `hard` (a real deadline) or
  `soft` (a target), or `期限: なし` / `なし` when there is none.
  Only real deadlines get dates; invented ones teach everyone to
  ignore all of them. The field names are Japanese in the production
  file (`期限` deadline, `状態` state, `担当` owner, `確認`
  last-checked, `経緯` history); keep the names and the order —
  the checker and every reader depend on them.
- `状態:` (state) — one of `ready`, `waiting_external`,
  `waiting_user`, `waiting_precondition`, `in_progress`, `done`.
  Overwritten on every flip, never appended.
- `担当:` (owner) — who holds the next step.
- `補足:` (note) or `待ち:` (waiting-on) — the current facts and
  evidence in one breath. No running log, no clock-time diary.
- `確認:` (last-checked) — the date this item's state was last
  verified against primary sources.

## Line 3 — history is links only

`経緯 →` followed by links to where the record lives: the log file's
section for this item, a case file, the decisive message or email.
No quoted text, no narrative. If it needs a paragraph, the paragraph
belongs in the log or the case file, and line 3 points at it.

## Rules the checker enforces

- An item is 3 lines — never more. Progress goes to `todo_log.md`.
- Line 2 carries the deadline, state and last-checked fields.
- Line 3 starts with `経緯 →` and contains no quoted text.
- A finished item (`- [x]`) never stays in `todo.md`; it moves to
  `todo_done.md` with its evidence.

Checks run **incrementally** against a base revision: only items
added or changed in the landing are judged, so adopting the format
never requires reformatting the whole file first.
