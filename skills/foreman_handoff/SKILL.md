---
name: foreman_handoff
description: "Prepare factory-handoff task files and F: instructions that pass the cap floor check and the template check, used whenever you hand a task to the Foreman."
---

<!-- Origin: the resident agent (agent-VM side), 2026-11-04. Tool paths in this skill are Muse-VM paths unless noted. -->

# Hand Work to the Foreman

## Price the cap from the executing session

- Declare `exec: fresh|long` in the frontmatter of every factory-handoff task file. An undeclared exec fails the check.

- Floor a fresh session task at 0.105M, and carry the fresh-session directive in the Instruction where the checker verifies it.

- Floor a long session task at 0.165M, priced at 0.055M per turn.

- Run `the setup tools directory/handoff_cap_check.py <task-file>` before sending the `F: repo task <id>` doorbell for a new task file, and require exit 0.

- Read the full procedure in records repo `docs/infra/handoff-cap-check-2026-11-03.md` when you need the record behind these steps.

## Check every instruction draft before sending

- Write every F: instruction draft to a file before you send anything.

- Run the draft through `the setup tools directory/foreman_instruction_check.py` and keep fixing and rechecking until the exit is 0.

- Treat any missing template section as a block on sending. The sections are the completion definition, the scope do and don't list, the risk enumeration, the hard cap, the 70% report, the stop condition, measured reporting, the report format and the escalation format.

- Build each draft from the template at `~/workspace/reference/foreman-instruction-template.md`.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
