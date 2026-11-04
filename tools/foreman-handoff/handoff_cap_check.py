#!/usr/bin/env python3
"""handoff_cap_check — floor check for factory-handoff task-file caps.

Lesson v1 (t00-cycle-test, 2026-11-03, failure-ledger signature
cap-ignores-fixed-turn-cost): a Foreman turn costs ~0.03-0.04M in fixed
terms regardless of the task, and even the shortest handoff cycle needs
at least 3 billable turns (receipt, work, completion). A cap set below
that floor is unmeetable from the start. Floor: cap >= 3 * 0.035 = 0.105M.

Lesson v2 (T92(0) + T89, 2026-11-03 evening — same signature, occurrences
2 and 3): the v1 rate was measured in a FRESH session, but execution kept
happening in the long-lived standby session, where a turn costs far more:
T92(0) ran ~0.047M/turn (0.14M cap vs ~0.33M actual), and the T89 gate
work read ~150k cache per turn (0.458M total vs the 0.45M cap, stopped
before its final step). A single rate is the bug: the floor must be
priced from the session that will actually execute.

Rule v2: every task file declares its execution session in frontmatter:
  exec: fresh  — the piece starts in a fresh Foreman session (the
                 doorbell/instruction must say so, and the Instruction
                 section must carry the fresh-session directive; the
                 checker verifies the directive is present). Rate
                 0.035M/turn, floor 0.105M.
  exec: long   — the piece runs in the existing long session. Rate
                 0.055M/turn (measured 0.047M + margin for ~150k cache
                 reads/turn), floor 0.165M.
Missing or unknown exec -> fail. Prefer fresh: long is the exception
that must justify itself in the cap, not the default.

Usage: handoff_cap_check.py <task-file.md> [more files...]
Prints one JSON line per file; exit 0 if every file passes, 1 otherwise.
"""

import json
import re
import sys

MIN_TURNS = 3
RATES_M = {"fresh": 0.035, "long": 0.055}
FRESH_DIRECTIVE = re.compile(r"fresh session|新しいセッション|新セッション", re.IGNORECASE)


def parse_frontmatter(text):
    m = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
    return m.group(1) if m else None


def parse_cap(fm):
    cm = re.search(r"^cap:\s*([0-9]*\.?[0-9]+)\s*M?\s*$", fm, re.MULTILINE)
    return float(cm.group(1)) if cm else None


def parse_exec(fm):
    em = re.search(r"^exec:\s*(\S+)\s*$", fm, re.MULTILINE)
    return em.group(1).lower() if em else None


def check(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return {"file": path, "verdict": "fail", "reason": f"unreadable: {e}"}
    fm = parse_frontmatter(text)
    if fm is None:
        return {"file": path, "verdict": "fail", "reason": "no frontmatter"}
    cap = parse_cap(fm)
    if cap is None:
        return {"file": path, "verdict": "fail", "reason": "no cap in frontmatter"}
    exec_mode = parse_exec(fm)
    if exec_mode not in RATES_M:
        return {
            "file": path, "cap_M": cap, "verdict": "fail",
            "reason": "frontmatter must declare exec: fresh or exec: long "
                      "(the cap floor is priced from the executing session; "
                      "v2 rule after T92(0)/T89, 2026-11-03)",
        }
    rate = RATES_M[exec_mode]
    floor = round(rate * MIN_TURNS, 3)
    if exec_mode == "fresh" and not FRESH_DIRECTIVE.search(text):
        return {
            "file": path, "cap_M": cap, "exec": exec_mode, "floor_M": floor,
            "verdict": "fail",
            "reason": "exec: fresh declared but the file carries no fresh-session "
                      "directive for the executor; without it the work lands in "
                      "the long session and the fresh rate is fiction",
        }
    implied_turns = round(cap / rate, 1)
    ok = cap + 1e-9 >= floor
    return {
        "file": path,
        "cap_M": cap,
        "exec": exec_mode,
        "rate_M": rate,
        "floor_M": floor,
        "implied_turns": implied_turns,
        "verdict": "pass" if ok else "fail",
        "reason": "" if ok else (
            f"cap {cap}M is below the {exec_mode}-session floor {floor}M "
            f"({MIN_TURNS} turns x {rate}M measured turn cost in that session); "
            "the cycle cannot fit even if the work itself is free"
        ),
    }


def main(argv):
    if len(argv) < 2:
        print(json.dumps({"verdict": "fail", "reason": "usage: handoff_cap_check.py <task-file.md> [...]"}))
        return 1
    rc = 0
    for path in argv[1:]:
        r = check(path)
        print(json.dumps(r, ensure_ascii=False))
        if r["verdict"] != "pass":
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
