---
name: failure_mechanisms
description: "Record failures in the ledger and close repeats with structural mechanisms that records repo documents, used whenever a failure or correction happens or you build a new tool, repo or mechanism."
---

<!-- Origin: the resident agent (agent-VM side), 2026-11-04. Tool paths in this skill are Muse-VM paths unless noted. -->

# Turn Failures into Mechanisms

## Record every failure in the same session

- Record every failure with `python3 the setup tools directory/failure_ledger.py add <signature> <note>` in the session where it happens. Failures include the operator's corrections, your own caught errors and Foreman or Codex catches.

- Reuse an existing signature for the same kind of failure. Run `python3 the setup tools directory/failure_ledger.py list` to see the signatures already in use.

- Read the full procedure in records repo `docs/infra/failure-ledger-2026-11-03.md` when you need the record behind these steps.

## Close a repeat with a structural mechanism

- Treat the task as unfinished on the second occurrence of a signature until a structural mechanism exists. A mechanism is a checker, a gate, or a template or checklist change, never a lesson in memory alone.

- Record the mechanism with `python3 the setup tools directory/failure_ledger.py resolve <signature> <mechanism>`.

- Escalate to the operator with the reason when a mechanism cannot be built, instead of leaving the repeat open.

- Know that HEARTBEAT runs `python3 the setup tools directory/failure_ledger.py check` every cycle and surfaces any unresolved repeat until it closes.

## Name every new mechanism in records repo

- Land a procedure doc naming the mechanism in records repo `docs/infra/` through the gates, in the same work block as the build, whenever you build a new repo, protocol or operated mechanism.

- Run `the setup tools directory/mechanism_coverage_check.py` to confirm coverage. The check default-denies every git repo under ~/workspace except records repo and every research topic holding a spec or trial doc.

- Read the full procedure in records repo `docs/infra/mechanism-coverage-2026-11-03.md` when you need the record behind these steps.

## Place rule fixes in the skill layer

- When the mechanism is a new or changed behavioral rule, write it into the body of the skill that owns that situation, never into the resident core of `~/AGENTS.md`.

- Mirror the same edit into the matching skill under records repo `skills/` in the same run, because the SoT copy is the single source and the Muse-side skill is its working cache.

- Create a new skill when no existing skill owns the situation, and add its row to the Map table in `~/AGENTS.md`.

- Admit a rule to the resident core only when it must fire unconditionally on every turn, and then as a single line whose detail lives in a skill.

- When the mechanism is a checker, a gate or a tool instead of a rule, follow the doc landing sections above.

## Keep every tool documented

- Name every script in `the setup tools directory/` and `beeper//`, plus anything wired into HEARTBEAT.md, in a landed doc under records repo `docs/infra/`.

- Run `the setup tools directory/doc_coverage_check.py` after adding a tool. The check fails on any uncovered script, and HEARTBEAT surfaces the miss within one heartbeat cycle.

- Land the procedure doc in the same session as the tool. The check sees existence, not quality, so hold quality at the land-time review.

- Respect the named exclusions for the one-off diagnostics from the 2026-11-01 Beeper OAuth sign-in, which are recorded in the checker and the health-tools doc.

## Available connectors

- GitHub connector docs for landing procedure docs in records repo.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
