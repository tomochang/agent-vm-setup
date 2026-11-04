#!/usr/bin/env python3
"""C8 action journal (standalone; production use NOT activated).

Intent/done journal for external actions with crash reconciliation.

Journal: JSONL, path via --journal. Module default is
~/workspace/beeper-diag/actions.jsonl (tests must pass a /tmp or
R/recovery path explicitly so no production-adjacent file is created).

Subcommands:
  intent --action A --target T --key K   append {ts,type:intent,action,target,key}
                                         (refuses a duplicate OPEN key, exit 2)
  done   --key K [--evidence E]          append {ts,type:done,key,evidence}
  reconcile                              print JSON of intents with no matching done:
                                         {key, action, target, age_sec,
                                          state:"unknown_outcome",
                                          disposition:"BLOCK-REPLAY"}
                                         Unknown outcomes are NEVER auto-retryable.
  list                                   print all well-formed entries, one JSON per line

Crash tolerance: a malformed line (e.g. a torn last line from a crash
mid-append) is ignored and counted (malformed_lines / warnings in
reconcile output); earlier entries stay intact.
Appends: open in append mode + flush + fsync. Stdlib only.
Importable: append_intent, append_done, read_journal, reconcile, list_entries.
"""
import argparse, json, os, sys
from datetime import datetime, timezone

DEFAULT_JOURNAL = os.environ.get("ACTION_JOURNAL_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "actions.jsonl"))


class DuplicateOpenKey(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc)


def _ts(dt=None):
    return (dt or _now()).isoformat(timespec="seconds")


def _parse_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _append(path, entry):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


def read_journal(path):
    """Return (entries, malformed_count). Missing file -> ([], 0)."""
    entries, malformed = [], 0
    if not os.path.exists(path):
        return entries, malformed
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict) or "type" not in obj:
                    raise ValueError("not a journal entry")
                entries.append(obj)
            except Exception:
                malformed += 1
    return entries, malformed


def open_intents(entries):
    done_keys = {e.get("key") for e in entries if e.get("type") == "done"}
    return [e for e in entries if e.get("type") == "intent" and e.get("key") not in done_keys]


def append_intent(path, action, target, key):
    entries, _ = read_journal(path)
    if any(e.get("key") == key for e in open_intents(entries)):
        raise DuplicateOpenKey(f"duplicate open key refused: {key}")
    return _append(path, {"ts": _ts(), "type": "intent", "action": action,
                          "target": target, "key": key})


def append_done(path, key, evidence=None):
    return _append(path, {"ts": _ts(), "type": "done", "key": key,
                          "evidence": evidence or ""})


def reconcile(path, now=None):
    """Dict: unknown_outcomes (BLOCK-REPLAY), counts, malformed warning count."""
    now = now or _now()
    entries, malformed = read_journal(path)
    unknown = []
    for e in open_intents(entries):
        ts = _parse_ts(e.get("ts"))
        age = int((now - ts).total_seconds()) if ts else None
        unknown.append({"key": e.get("key"), "action": e.get("action"),
                        "target": e.get("target"), "age_sec": age,
                        "state": "unknown_outcome", "disposition": "BLOCK-REPLAY",
                        "note": "never auto-retry; a human/agent must verify the real-world outcome first"})
    return {"journal": path, "unknown_outcomes": unknown,
            "unknown_count": len(unknown), "malformed_lines": malformed,
            "warnings": malformed, "entries": len(entries)}


def list_entries(path):
    entries, malformed = read_journal(path)
    return {"entries": entries, "malformed_lines": malformed}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", default=DEFAULT_JOURNAL)
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("intent"); pi.add_argument("--action", required=True)
    pi.add_argument("--target", required=True); pi.add_argument("--key", required=True)
    pd_ = sub.add_parser("done"); pd_.add_argument("--key", required=True)
    pd_.add_argument("--evidence", default="")
    sub.add_parser("reconcile"); sub.add_parser("list")
    a = p.parse_args(argv)
    if a.cmd == "intent":
        try:
            e = append_intent(a.journal, a.action, a.target, a.key)
        except DuplicateOpenKey as ex:
            print(str(ex), file=sys.stderr); return 2
        print(json.dumps(e, ensure_ascii=False))
    elif a.cmd == "done":
        print(json.dumps(append_done(a.journal, a.key, a.evidence), ensure_ascii=False))
    elif a.cmd == "reconcile":
        print(json.dumps(reconcile(a.journal), ensure_ascii=False, indent=1))
    elif a.cmd == "list":
        for e in list_entries(a.journal)["entries"]:
            print(json.dumps(e, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
