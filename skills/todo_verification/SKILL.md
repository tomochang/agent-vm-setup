---
name: todo_verification
description: "Settle a todo entry's outcome against Beeper, Google Calendar and Gmail before changing it, used whenever you clean up, move or fix todo entries."
---

<!-- Origin: the resident agent (agent-VM side), 2026-11-04. Tool paths in this skill are Muse-VM paths unless noted. -->

# Verify Todo Outcomes Against Three Sources

## Never settle an outcome from the todo text

- Check the relevant Beeper chat before moving or fixing any todo entry. Read Beeper through `beeper//beeper_api.py` and paginate the chat to the end.

- Check the Google Calendar events around the entry's dates.

- Check Gmail for confirmations and cancellations.

- Mark the entry 未確認 when all three checks leave the outcome unresolved, and never mark it done.

## Let the weekly sweep draft the cleanup

- Know that the `stale_todo_rows` signal in `improvement_scout.py` flags past-dated rows and overdue items.

- Let the improvement-scout cron draft the cleanup proposal with per-entry evidence.

- Execute the cleanup in the main chat only after the operator's OK, and land it through the gates.

- Read the full procedure in records repo `docs/infra/improvement-scout-2026-11-03.md` when you need the record behind these steps.

## Available connectors

- Gmail connector docs for confirmations and cancellations.

- Google Calendar connector docs for the events around an entry's dates.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
