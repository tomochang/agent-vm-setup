#!/usr/bin/env python3
"""calendar_block — show the full event block around a calendar event.

Born from the 2026-11-03 miss: a dinner's start moved 19:00 ->
19:30 and only the main event was patched; the linked movement events
(before/after) stayed behind, leaving the block inconsistent, and
the operator had to fix it himself. Another dinner two days earlier had
been handled correctly (movements renamed/shifted together), so the
failure was inconsistency, not ignorance — the fix is to make the
block visible mechanically before any time change.

Usage: calendar_block.py <eventId> [window_hours=4]
Prints the anchor event and every primary-calendar event overlapping
[start-window, end+window], in start order, one line each:
  HH:MM -> HH:MM | summary | id
Run it BEFORE patching an event's time and AGAIN after, to verify the
block (main + movement events) is contiguous and consistent.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

CLI = os.environ.get("GWS_CLI", "hatch_gws_cli")
JST = timezone(timedelta(hours=9))


def run(args):
    r = subprocess.run([CLI] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"calendar_block: CLI failed: {r.stderr.strip()[:300]}")
        sys.exit(2)
    return json.loads(r.stdout)


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    event_id = sys.argv[1]
    window = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
    ev = run(["calendar", "events", "get", "--params",
              json.dumps({"calendarId": "primary", "eventId": event_id})])
    start = parse(ev["start"]["dateTime"])
    end = parse(ev["end"]["dateTime"])
    lo = (start - timedelta(hours=window)).astimezone(JST).isoformat()
    hi = (end + timedelta(hours=window)).astimezone(JST).isoformat()
    lst = run(["calendar", "events", "list", "--params",
               json.dumps({"calendarId": "primary", "timeMin": lo, "timeMax": hi,
                           "singleEvents": True, "orderBy": "startTime"})])
    for e in lst.get("items", []):
        s, en = e["start"], e["end"]
        mark = " <==" if e["id"] == event_id else ""
        print(f"{s.get('dateTime', s.get('date'))} -> {en.get('dateTime', en.get('date'))} "
              f"| {e.get('summary')} | {e['id']}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
