# Watchers — replies get noticed by a script, not by luck

A pattern, not a shipped script: the poll/wake mechanics and the
state it keeps (a fingerprint of the last-seen message per chat,
plus the coverage registry the health loop checks) are specified
below; the implementation is a short script per deployment.

The failure this prevents: a counterpart (another agent, an external
executor) replies in a chat, and nobody notices until the human asks
"did they answer?" — sometimes days later. It happened three times
in one day before this pattern existed.

## Shape

A watcher is a **poll script plus a wake**, per watched chat:

1. **Detect (script, no model).** Every ~2 minutes the script reads
   the chat's newest messages through the local API and compares a
   fingerprint set against its state file. Posts from the human or
   the agent itself are skipped. Only genuinely new counterpart
   posts produce a wake; duplicates never re-fire.
2. **Deliver (verbatim relay).** The wake carries the new posts, and
   the woken worker's entire job is to pass them on **exactly as
   written** — sender, timestamp, full text. The worker does not
   summarize, classify, decide, or act.

Why no interpretation on the relay path: an interpreting worker is a
second, context-poor judge in the middle of the pipe. In production
it produced stale summaries of already-resolved matters that the
main agent then had to filter. A verbatim relay cannot silently
misjudge — the worst it can do is deliver text the main agent can
see for itself. All judgment happens where the context is.

## The watcher must itself be watched

The meta-failure is a channel whose watcher was never attached, or
silently died — indistinguishable from "no news" until the human
notices. So the health loop includes a **coverage check**: a registry
of work channels (chat → watcher); any channel with a counterpart
post in the last 72 hours whose watcher is missing or disabled is a
failing check, surfaced like any other health failure.

Rule that follows: **when a work thread opens on a new channel,
attach its watcher in the same work block** — and add it to the
coverage registry.

## Cost note

Detection is a few API calls per cycle — no model tokens. The only
model cost is one woken worker per *actual* new post, and the relay
instruction keeps that turn minimal.
