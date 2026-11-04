---
name: trip_design_brief
description: "Frame itinerary options from the generated window brief after a premise audit, used whenever you design or reshape a trip or propose itinerary options."
---

<!-- Origin: the resident agent (agent-VM side), 2026-11-04. Tool paths in this skill are Muse-VM paths unless noted. -->

# Design a Trip from the Window Brief

## Generate and read the brief first

- Run `the setup tools directory/trip_window_dump.py --from <start> --to <end> [--plan <master-plan file>]` for the trip window before you propose any itinerary shape.

- Read the output in full. The brief carries the Google Calendar for the window, the records repo trip master plan and the todo travel section.

## Audit the premises before drawing options

- Sort every element of the window into mandatory and not mandatory at step 0, before you frame any option.

- Treat other people's calendar blocks as fixed rails. Move only the operator's solo logistics.

- Treat existing bookings as sunk costs, not rails.

- Read the full procedure in records repo `docs/infra/trip-window-dump-2026-11-04.md` when you need the record behind these steps.

## Available connectors

- Google Calendar connector docs for the window's events behind the brief.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
