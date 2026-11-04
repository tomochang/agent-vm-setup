---
name: clawd_sot_landing
description: "Mirror real-world facts into records repo and land them through the gates in the same run, used whenever you record a booking, cancellation, completion or decision or classify a todo matter."
---

<!-- Origin: the resident agent (agent-VM side), 2026-11-04. Tool paths in this skill are Muse-VM paths unless noted. -->

# Land Facts in records repo, the Source of Truth

## Treat records repo as the record

- Treat Muse-side files such as agent-todo items, the INDEX, MEMORY.md and cron state as a working cache, never as the record.

- Mirror every real-world fact into the matching records repo file and land it through the gates in the same run or session. Facts include bookings, cancellations, task-ownership corrections, completions and user decisions.

- Create a Google Calendar event for every booking, and delete or correct the event when the booking is cancelled or changed.

## Read the source of truth deeply

- Read the current `private/todo.md` in full before classifying or reporting on any todo matter.

- Read the item's section in `private/todo_log.md` as well.

- Never classify or report from grep hits or snippets of these files.

## Land through the gates

- Follow the commit rules and gate flow recorded in records repo's own AGENTS.md and SHARED_RULES.md for every land.

- Finish the land in the same session as the work that produced the fact.

## Write the procedure for environment work

- Produce a reproduction-grade procedure doc in records repo `docs/` for environment or infrastructure work, in the same session as the work.

- Include the packages, the exact commands, the full script contents or diffs, the verification steps and the known-untested paths.

- Land the doc through the gates so another environment can rebuild the setup from the document alone.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for work in the records repo repository.

- [Google Calendar](/opt/hatch/connectors/google_calendar/CONNECTOR.md) for the booking events this skill requires.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
