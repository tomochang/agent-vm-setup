---
name: calendar_blocks
description: "Move a calendar event's linked travel blocks with it and verify contiguity afterwards, used whenever you change the time of an event that has movement events."
---

<!-- Origin: the resident agent (agent-VM side), 2026-11-04. Tool paths in this skill are Muse-VM paths unless noted. -->

# Move a Calendar Event With Its Whole Block

## See the block before you patch

- Run `the setup tools directory/calendar_block.py <eventId>` to see the event and its linked movement events before you change any time.

## Move every linked event in the same operation

- Patch the main event and every linked 移動・前 and 移動・後 event together whenever the time changes.

## Verify the block afterwards

- Run `the setup tools directory/calendar_block.py <eventId>` again after patching and confirm the block runs continuously.

- Read the full procedure in records repo `docs/infra/calendar-block-2026-11-03.md` when you need the record behind these steps.

## Available connectors

- Google Calendar connector docs for reading and patching the events.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
