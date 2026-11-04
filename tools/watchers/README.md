# Watchers — wake the agent when a counterpart replies

One watcher per chat that carries work: it polls the Beeper Desktop
API every couple of minutes and, when the counterpart posts, wakes
the agent with the posts. The worker that receives the wake payload
relays the posts **verbatim** — no summary, interpretation, or
classification on the relay path. Judgment lives in the main chat.

## Instantiate

```sh
cp tools/watchers/chat-watch.sh.template ~/hooks/scripts/<hook-id>-watch.sh
```

Then set, per hook, in the hook's environment or definition:

- `WATCH_CHAT_ID` — the Beeper chat id to watch (required).
- `WATCH_STATE_FILE` — fingerprint state file (default
  `~/hooks/state/chat-watch.json`; use one file per hook).
- `OPERATOR_SENDER_PREFIX` — the operator's own sender id prefix
  (default `@operator`); the operator's own messages are not news.
- `BEEPER_API_DIR` — directory holding `beeper_api.py` (default:
  this repo's `beeper/`).

## Register coverage

Add the channel + hook to `tools/channel-watch/channel_watch_check.py`
in the same step, and run the check from the health loop: a
counterpart channel with recent posts and no enabled watcher is a
FAIL. See `workflows/watchers.md` for the pattern.
