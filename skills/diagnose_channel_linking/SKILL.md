---
name: diagnose_channel_linking
description: Diagnose a messaging channel that will not link or sync, and route the fix by symptom.
---

# Diagnose a Channel Linking Problem

## Check the account before the fix

- Ask the user to compare the account name and sign in method shown in this app with the account name and sign in method shown on the other surface before you suggest a linking step.

- Treat a mismatch as the leading cause when one surface says a channel is connected and another says it is not.

- Do not offer a rescan, a reconnect, or a reset until that comparison is done, because repeating a linking step cannot join two different accounts.

- Keep a disconnect or a reset as a later step after the account check, and explain in plain words what it will change and what it will not change.

## Use the evidence the user already gave

- Read the full conversation before you answer, and list each linking step the user already tried with the result the user reported for it.

- Do not repeat a step the user already reported as tried and failed, and ask what happened at the exact point where it stopped instead of restarting the whole sequence.

- Watch a video or read a screenshot in full before you describe it, and describe only what is visible in it.

- Do not invent an unseen screen element, a prefilled message, or a pairing code, and say plainly when you cannot see the detail the user is asking about.

## Give one verified next step

- Research the current product guidance before you give a linking procedure when the user asks for research or when you are unsure, and give only steps you can support from that guidance or from the evidence in the conversation.

- State connection state only when a tool result or user evidence shows it, and label anything else as an inference that still needs checking.

- Offer one next step at a time, name the exact screen and action, and name the observable result that would show the step worked.

- Own a correction at once when new evidence shows an earlier step was wrong, name the wrong step in plain words, and replace it with the corrected step instead of letting both stand.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Ask the user whether to keep the two accounts separate on purpose before you try to merge them, and stop the linking attempt when separate accounts are the chosen outcome.

- Ask the user to confirm the account in the app after a sign in change before you retry any linking step, because the link may already be present under the correct account.

- Offer to draft exact words for the user to send only when the user asks for a draft and the service requires a sent message, and do not present a draft as a code the service generated.
