#!/usr/bin/env python3
"""channel_watch_check — every active counterpart work channel must have an
enabled reply watcher, so replies never pile up unread until the operator relays
them by hand.

Born 2026-11-04 (failure ledger: counterpart-reply-not-watched, 3 misses in
one day on the a counterpart channel). The sora-watch hook fixed that one channel; this
check is the self-recognition layer: it compares the registry of work
channels (where a counterpart's reply carries work) against the hook
definitions on disk, and fails when an active channel's watcher is missing
or disabled.

Registry rule: when a work thread is opened on a new counterpart/agent
channel, add the channel + its watcher hook here in the same work block
(see clawd docs/infra/mofu-sora-watch-2026-11-04.md).

Exit 0 = all active channels watched (or Beeper unreachable — the liveness
check owns that failure). Exit 1 = at least one FAIL line.
Test hook: CHANNEL_WATCH_FORCE_MISSING=<hook-id> pretends that hook is
absent, to prove the FAIL path fires.
"""
import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.environ.get("BEEPER_API_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "beeper")))

# Register the channels whose counterpart replies carry work, as
# (display name, beeper chat id, watcher hook id). The shipped default
# is empty on purpose: with no channels registered the check reports OK
# and does nothing. Example entry:
#   ("Example counterparty", "<BEEPER_CHAT_ID>", "example-watch"),
CHANNELS = []
ACTIVE_WITHIN = timedelta(hours=72)
DEF_DIR = os.path.expanduser("~/hooks/definitions")


def watcher_enabled(hook_id):
    if os.environ.get("CHANNEL_WATCH_FORCE_MISSING") == hook_id:
        return False
    try:
        with open(os.path.join(DEF_DIR, hook_id + ".json")) as f:
            return json.load(f).get("enabled") is True
    except Exception:
        return False


def last_counterpart_ts(beeper_api, chat_id):
    data = beeper_api.get(
        "/v1/chats/" + urllib.parse.quote(chat_id, safe="") + "/messages",
        params={"limit": 15},
    )
    newest = None
    for m in data.get("items", []):
        if (m.get("senderID") or "").startswith("@operator"):
            continue
        ts = m.get("timestamp")
        if ts and (newest is None or ts > newest):
            newest = ts
    return newest


def main():
    try:
        import beeper_api
    except BaseException as e:
        print(f"SKIP beeper helper unavailable: {e}")
        return 0

    now = datetime.now(timezone.utc)
    fails = 0
    for name, chat_id, hook_id in CHANNELS:
        try:
            newest = last_counterpart_ts(beeper_api, chat_id)
        except BaseException:
            print(f"SKIP {name}: beeper unreachable (liveness check owns this)")
            continue
        active = False
        if newest:
            ts = datetime.fromisoformat(newest.replace("Z", "+00:00"))
            active = (now - ts) <= ACTIVE_WITHIN
        if not active:
            print(f"OK {name}: no counterpart post in 72h (watcher state irrelevant)")
            continue
        if watcher_enabled(hook_id):
            print(f"OK {name}: active and watcher '{hook_id}' enabled")
        else:
            print(f"FAIL {name}: counterpart posted within 72h but watcher '{hook_id}' is missing or disabled")
            fails += 1
    if fails:
        print(f"channel_watch_check: FAIL ({fails} unwatched active channel(s))")
        return 1
    print("channel_watch_check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
