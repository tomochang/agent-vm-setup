# Workflows — the patterns that connect the pieces

The components (inbox, records repo, todo, health loop) become a
system through a few recurring workflows:

| Workflow | What it does |
|---|---|
| [watchers.md](watchers.md) | Notice a counterpart's reply within minutes — detection by script, interpretation by nobody |
| [gates.md](gates.md) | Land every records change through a checked, reviewable flow; never write to the shared branch directly |
| [handoff.md](handoff.md) | Give a worker agent a task as a file in git, with a doorbell message and a cost cap |
| [improvement-loop.md](improvement-loop.md) | A periodic pass that turns signals into a few small, finished improvements |

Shared principles:

- **Deterministic first.** Anything a script can decide, a script
  decides. Model judgment is spent where judgment is the work.
- **One surface owns one fact.** The records repo is the only place
  state lives; every other surface is a working cache.
- **Completion is verified, not reported.** A confirmation, an API
  response, or a read-back — never a worker's summary.
