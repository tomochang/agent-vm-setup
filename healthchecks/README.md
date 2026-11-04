# Dead man's switch (healthchecks.io)

Purpose: if the VM dies silently, the human hears about it from
someone other than the dead VM. healthchecks.io expects a ping on a
schedule; a missing ping triggers an email alert.

## Setup

1. Free account at healthchecks.io. An agent can complete the whole
   flow itself through the emailed login link (read from the connected
   mailbox, opened in the agent's browser) — no password to invent.
2. Create a check matching your health loop's cadence, e.g.
   period 30 min (`*/30 * * * *`), grace 15 min, email notifications on.
3. Store secrets in `~/.config/healthchecks/credentials` (mode 600),
   one `key=value` per line: the ping URL, and — only if you run a
   judge — a **read-only** API key. Never in git, never in chat.

## Wiring

- The health loop pings **first, unconditionally**, every iteration:
  `curl -s --max-time 30 "$(grep ^ping_url= ~/.config/healthchecks/credentials | cut -d= -f2-)"`
- Verify after setup: test ping returns `OK`, and the API shows the
  check as `up`.

## The judge pattern (multi-agent setups)

A read-only consumer on another machine can poll check states via the
API (e.g. every 15 min) and alert on transitions — an independent
witness that does not share the pinging VM's fate.

## Hard-won warning

**Rotating the read-only API key revokes the old one everywhere.**
Every consumer of the old key (like another agent's judge) starts
getting 401s immediately. If a key must be replaced:

1. Warn the other consumers first, via the records repo.
2. Hand the new key to each consumer encrypted to a fresh public key
   they generated for that purpose (RSA-OAEP, base64) — never as
   plaintext in chat, email, or git.
3. Record the rotation and its confirmation in the records repo.
