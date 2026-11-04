# Skills — rule bodies that load only when the situation matches

A **skill** is a self-contained procedure for one recurring
situation, stored as `skills/<name>/SKILL.md` in the records repo:

```markdown
---
name: verify-todo-outcomes
description: Settle a todo item's outcome against primary sources before changing it.
---

# Body: the procedure, its evidence rules, and its failure cases.
```

The agent searches the skill catalog by name and description, reads
the matching `SKILL.md` **in full**, and follows it. Nothing else
loads. That economy is the point.

## Why not put the rules in the resident file?

The resident instruction file (`AGENTS.md`) is read on every turn.
Two failure modes follow:

- Rules buried in the middle of a long resident file stop firing —
  they are present but effectively lost.
- Carrying every procedure at all times wastes context on situations
  that are not happening.

So the resident file holds only **a short core plus a map**: a few
principles that apply to every turn, and a table of
*situation → skill*. Everything else lives in skills, selected
just-in-time. When a new rule is learned, it goes into the owning
skill's body — never into the resident file.

## Authoring rules

- **One situation per skill.** If the trigger can't be stated in one
  line ("when X happens", "before doing Y"), it isn't a skill yet.
- **The description is the trigger.** Write it as the matching rule
  an agent (or a search) would use: what situation, what action.
  Vague descriptions mean the skill never fires.
- **Self-contained.** The body carries the full procedure, the
  evidence standard, and the known failure cases — the reader should
  not need the conversation that produced it.
- **Fixes land in the owning skill.** When a failure traces back to a
  procedure, the correction goes into that skill's body in the same
  change, not into a chat note or the resident file.
- **Small and concrete beats general.** Extract the pattern only
  after the concrete version works.

## Multi-surface setups

When the same human is served from several surfaces (an app, a web
chat, a CLI), the skill bodies live **once** in the records repo.
Other surfaces keep *thin pointer skills*: a stub with the same name
and description whose body says "pull the records repo and read
`skills/<name>/SKILL.md` in full". If a surface's copy and the repo
disagree, the repo wins.

An example skill ships in [examples/](examples/).
