#!/usr/bin/env python3
"""Failure ledger — two occurrences of the same failure force a mechanism.

Standard library only. See health/ and SETUP.md Phase 5 for how the
ledger is wired into the health loop.

Ledger: failure-ledger.jsonl in the same directory as this script
(override: FAILURE_LEDGER_PATH)
Events:
  occurrence {ts, signature, note}
  mechanism  {ts, signature, mechanism}
Unresolved = a signature with >= 2 occurrences and no mechanism event.
`check` exits 1 while any unresolved signature exists.

Usage:
  failure_ledger.py add <signature> <note...>
  failure_ledger.py resolve <signature> <mechanism...>
  failure_ledger.py check
  failure_ledger.py list
"""
import json
import os
import sys
from datetime import datetime, timezone

LEDGER = os.environ.get(
    "FAILURE_LEDGER_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "failure-ledger.jsonl"),
)


def load():
    events = []
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


def append(event):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def summarize(events):
    occ, mech = {}, {}
    for e in events:
        sig = e.get("signature", "")
        if e.get("type") == "occurrence":
            occ.setdefault(sig, []).append(e)
        elif e.get("type") == "mechanism":
            mech.setdefault(sig, []).append(e)
    return occ, mech


def unresolved(events):
    occ, mech = summarize(events)
    return sorted(
        sig for sig, evs in occ.items() if len(evs) >= 2 and sig not in mech
    )


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "add":
        if len(argv) < 4:
            print("usage: add <signature> <note...>", file=sys.stderr)
            return 2
        sig = argv[2]
        append({"type": "occurrence", "ts": now_iso(), "signature": sig,
                "note": " ".join(argv[3:])})
        events = load()
        occ, _ = summarize(events)
        state = "mechanism_required" if sig in unresolved(events) else "recorded"
        print(json.dumps({"ok": True, "signature": sig,
                          "occurrences": len(occ.get(sig, [])), "state": state},
                         ensure_ascii=False))
        return 0
    if cmd == "resolve":
        if len(argv) < 4:
            print("usage: resolve <signature> <mechanism...>", file=sys.stderr)
            return 2
        append({"type": "mechanism", "ts": now_iso(), "signature": argv[2],
                "mechanism": " ".join(argv[3:])})
        print(json.dumps({"ok": True, "signature": argv[2], "state": "resolved"},
                         ensure_ascii=False))
        return 0
    if cmd == "check":
        un = unresolved(load())
        print(json.dumps({"ok": not un, "unresolved": un}, ensure_ascii=False))
        return 0 if not un else 1
    if cmd == "list":
        events = load()
        occ, mech = summarize(events)
        for sig in sorted(set(occ) | set(mech)):
            print(f"{sig}: occurrences={len(occ.get(sig, []))} "
                  f"mechanism={'yes' if sig in mech else 'no'}")
            for e in occ.get(sig, []):
                print(f"  - {e['ts']} occurrence: {e.get('note', '')}")
            for e in mech.get(sig, []):
                print(f"  - {e['ts']} mechanism: {e.get('mechanism', '')}")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
