# Handoff — tasks for a worker agent, as files in git

For heavy work on a second machine (a coding agent with its own
daemon), the task itself is a file in a git repo — not a chat
message that scrolls away.

## The task file

```markdown
---
id: t90-a
state: ready
created: 2026-11-04
updated: 2026-11-04
cap: 0.20M
exec: fresh
---

## Instruction
<written by the assigning agent only: scope, premises to verify
first, risks, the exact closure conditions>

## Reports
<appended by the worker only, ending with a Cost line>
```

- **States**: `ready → working → input-required | done | failed`.
  Only the worker moves its own state; only the assigner edits the
  Instruction.
- **cap** is a hard budget in the worker's cost units, with a
  mid-work report due at ~70%. A piece that would exceed its cap
  stops and reports — it never quietly overruns.
- **exec** declares the session shape (`fresh` for short pieces,
  `long` for continuing ones), because fixed per-session costs make
  the honest budget floor different for each.

## The doorbell

Git carries the task; a one-line message in the shared chat starts
it: the worker acts only on messages with the agreed prefix (e.g.
`F: repo task <id>`), plus two exact-match channel commands
(`F: stop all`, `F: resume all`) whose semantics are rehearsed, not
assumed.

## Closure is three things, not one

A piece is closed only when **all** of these hold:

1. The work is merged to the handoff repo's main.
2. The trial/record entry in the records repo is updated and landed
   through the gates.
3. Both commit identifiers are reported together.

Anything less leaves the next session unable to tell what actually
finished — the exact ambiguity the file-based protocol exists to
remove.
