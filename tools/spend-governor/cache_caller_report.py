#!/usr/bin/env python3
"""Caller-split prompt-cache report for VM-local Claude Code CLI sessions.

WHY: the cache-efficiency research (records research/cache-efficiency, Lv3
claim #4) found that an AVERAGE cache hit rate hides the callers that never
share a prefix -- in one measured case an average of 77% sat next to cron
callers at ~0%. This tool aggregates the official confirmation fields
(usage.cache_creation with its ephemeral_1h / ephemeral_5m split, plus
cache_read_input_tokens) from Claude Code session JSONL logs, split BY
CALLER, so each delegation class can be judged on its own numbers.

COVERAGE GAP (read first): this covers ONLY Claude Code CLI sessions run
in this VM (~/.claude/projects/*/*.jsonl). Muse chat / cron-agent tokens
are NOT in these logs. A caller missing here means "not measured", never
"zero usage". In particular, the 30-minute crons (beeper-todo-sync,
todo-auto-advance) run as Muse-side agents; they appear here ONLY when
they delegate to the VM's Claude Code CLI.

METHOD: parsing reuses ~/workspace/tools/usage_report.py (imported for its
timestamp/token helpers and its skipbit dedupe rule: group usage records
by message.id, keep the record whose four token fields sum to the
maximum, because streamed partials repeat usage cumulatively). Unlike
usage_report.py's per-day aggregate, attribution needs session linkage,
so this tool keeps, per deduped message, its session file, and reads the
cache_creation ephemeral split that usage_report.py does not retain.

CALLER ATTRIBUTION (per session, from signals in the log itself):
  - cron-beeper-todo-sync / cron-todo-auto-advance: the session's first
    user message names the cron (fingerprints below). Zero matches is a
    reportable result, not an error.
  - probe-ladder-check: first user message starts "Reply with exactly:".
  - task-agent-todo-index: first user message fingerprints the
    agent-todo-items indexing task.
  - delegation-discussion: cwd under a discussion project dir, or a
    brief-style first message (READ-ONLY analysis / BRIEF.md / Round 1).
  - unknown: everything else. Unknown sessions are NEVER dropped or
    force-attributed; they are reported as their own bucket.

HIT RATE (defined here, used consistently):
  hit_rate = cache_read / (cache_read + cache_creation + input_tokens)
  over deduped messages. input_tokens is the uncached remainder.

EPHEMERAL MIX matters beyond this report: the spend governor weights all
cache writes at 1.25 (the 5-minute TTL price). The 1h/5m split printed
here is the evidence for whether that weight matches reality (1h writes
really cost 2x base input).

Usage:
  python3 cache_caller_report.py            # readable table
  python3 cache_caller_report.py --json     # one-line JSON summary
  python3 cache_caller_report.py --projects DIR
Python 3 stdlib only. Read-only against the logs.
"""
import argparse
import glob
import importlib.util
import json
import os
import sys
from collections import defaultdict

_ur_spec = importlib.util.spec_from_file_location(
    "usage_report", os.path.expanduser("~/workspace/tools/usage_report.py"))
ur = importlib.util.module_from_spec(_ur_spec)
_ur_spec.loader.exec_module(ur)

COVERAGE_NOTE = ("VM-local Claude Code CLI only; Muse chat/cron-agent "
                 "tokens are not in these logs (missing != zero usage)")

# (caller, predicate(session)) -- evaluated in order; first match wins.
def _first_text(sess):
    return sess["first_user"] or ""


def _is_cron(name):
    return lambda s: name in _first_text(s)


CALLER_RULES = [
    ("cron-beeper-todo-sync", _is_cron("beeper-todo-sync")),
    ("cron-todo-auto-advance", _is_cron("todo-auto-advance")),
    ("probe-ladder-check",
     lambda s: _first_text(s).startswith("Reply with exactly:")),
    ("task-agent-todo-index",
     lambda s: "agent-todo-items" in _first_text(s)
     and "markdown table" in _first_text(s)),
    ("delegation-discussion",
     lambda s: ("projects/factory" in (s["cwd"] or "")
                or "foreman-cache-discussion" in (s["cwd"] or "")
                or _first_text(s).startswith("READ-ONLY analysis")
                or "BRIEF.md" in _first_text(s)[:40]
                or _first_text(s).startswith("# Round 1"))),
]


def classify(sess):
    for name, pred in CALLER_RULES:
        try:
            if pred(sess):
                return name
        except Exception:
            continue
    return "unknown"


def first_user_text(obj):
    if obj.get("type") != "user":
        return None
    m = obj.get("message")
    if not isinstance(m, dict):
        return None
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        for part in c:
            if isinstance(part, dict) and part.get("type") == "text":
                return part.get("text") or ""
    return None


def scan_sessions(projects_dir):
    """Return {session_path: {cwd, first_user, messages: {mid: usage_rec}}}.

    Dedupe mirrors usage_report.py (skipbit): per message.id keep the
    record whose input+output+cache_read+cache_creation sum is largest.
    """
    sessions = {}
    for path in sorted(glob.glob(os.path.join(projects_dir, "*", "*.jsonl"))):
        sess = {"cwd": None, "first_user": None, "messages": {}}
        try:
            fh = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, RecursionError):
                    continue
                if not isinstance(obj, dict):
                    continue
                if sess["cwd"] is None and obj.get("cwd"):
                    sess["cwd"] = obj["cwd"]
                if sess["first_user"] is None:
                    t = first_user_text(obj)
                    if t:
                        sess["first_user"] = t
                msg = obj.get("message")
                if not isinstance(msg, dict) or not isinstance(
                        msg.get("usage"), dict):
                    continue
                u = msg["usage"]
                mid = msg.get("id")
                if not mid or ur.jst_date(obj.get("timestamp")) is None:
                    continue
                vals = tuple(ur.tok(u, f) for f in ur.TOKEN_FIELDS)
                total = sum(vals)
                cc = u.get("cache_creation") or {}
                rec = {
                    "date": ur.jst_date(obj.get("timestamp")),
                    "input": vals[0], "output": vals[1],
                    "read": vals[2], "creation": vals[3],
                    "eph_1h": ur.tok(cc, "ephemeral_1h_input_tokens"),
                    "eph_5m": ur.tok(cc, "ephemeral_5m_input_tokens"),
                    "model": msg.get("model"),
                    "total": total,
                }
                cur = sess["messages"].get(mid)
                if cur is None or total > cur["total"]:
                    sess["messages"][mid] = rec
        if sess["messages"]:
            sessions[path] = sess
    return sessions


def aggregate(sessions):
    """{(caller, date): counters} plus per-caller session counts."""
    agg = defaultdict(lambda: dict(calls=0, input=0, output=0, read=0,
                                   creation=0, eph_1h=0, eph_5m=0))
    sess_count = defaultdict(int)
    for sess in sessions.values():
        caller = classify(sess)
        sess_count[caller] += 1
        for rec in sess["messages"].values():
            row = agg[(caller, rec["date"])]
            row["calls"] += 1
            for k in ("input", "output", "read", "creation",
                      "eph_1h", "eph_5m"):
                row[k] += rec[k]
    return agg, sess_count


def hit_rate(row):
    denom = row["read"] + row["creation"] + row["input"]
    return (row["read"] / denom) if denom else None


def fmt(n):
    return f"{n:,}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true",
                    help="print a one-line JSON summary instead of a table")
    ap.add_argument("--projects", default=os.path.expanduser(
        "~/.claude/projects"), help="Claude projects dir")
    args = ap.parse_args(argv)

    sessions = scan_sessions(args.projects)
    agg, sess_count = aggregate(sessions)

    callers = {}
    for (caller, date), row in sorted(agg.items()):
        c = callers.setdefault(caller, dict(
            sessions=sess_count.get(caller, 0), calls=0, input=0, output=0,
            read=0, creation=0, eph_1h=0, eph_5m=0, days={}))
        for k in ("calls", "input", "output", "read", "creation",
                  "eph_1h", "eph_5m"):
            c[k] += row[k]
        c["days"][date] = dict(row, hit_rate=hit_rate(row))
    for c in callers.values():
        c["hit_rate"] = hit_rate(c)
        tot = c["eph_1h"] + c["eph_5m"]
        c["eph_1h_share"] = (c["eph_1h"] / tot) if tot else None

    # Cron callers are first-class rows even at zero matches: their
    # ABSENCE from the logs is a finding (cron work happens on the Muse
    # platform; only CLI delegations would appear here), so never let a
    # zero-match cron caller silently vanish from the output.
    for name in ("cron-beeper-todo-sync", "cron-todo-auto-advance"):
        callers.setdefault(name, dict(
            sessions=0, calls=0, input=0, output=0, read=0, creation=0,
            eph_1h=0, eph_5m=0, days={}, hit_rate=None, eph_1h_share=None))

    grand = dict(calls=0, input=0, output=0, read=0, creation=0,
                 eph_1h=0, eph_5m=0)
    for c in callers.values():
        for k in grand:
            grand[k] += c[k]
    grand["hit_rate"] = hit_rate(grand)
    tot = grand["eph_1h"] + grand["eph_5m"]
    grand["eph_1h_share"] = (grand["eph_1h"] / tot) if tot else None
    dates = sorted({d for c in callers.values() for d in c["days"]})

    if args.json:
        out = {
            "coverage": COVERAGE_NOTE,
            "dates": dates,
            "sessions": sum(sess_count.values()),
            "overall": grand,
            "callers": {k: {kk: vv for kk, vv in v.items() if kk != "days"}
                        for k, v in sorted(callers.items())},
        }
        print(json.dumps(out, ensure_ascii=False))
        return 0

    print("Caller-split prompt-cache report (Claude Code CLI, this VM)")
    print("Coverage:", COVERAGE_NOTE)
    print("Dates (JST):", ", ".join(dates) if dates else "(none)")
    print("Hit rate = cache_read / (cache_read + cache_creation + input)")
    print()
    hdr = (f"{'caller':<26} {'sess':>4} {'calls':>5} {'cache_read':>11} "
           f"{'creation':>10} {'eph_1h':>10} {'eph_5m':>8} {'input':>7} "
           f"{'hit':>6}")
    print(hdr)
    print("-" * len(hdr))
    for caller in sorted(callers):
        c = callers[caller]
        hr = f"{c['hit_rate']:.1%}" if c["hit_rate"] is not None else "-"
        print(f"{caller:<26} {c['sessions']:>4} {c['calls']:>5} "
              f"{fmt(c['read']):>11} {fmt(c['creation']):>10} "
              f"{fmt(c['eph_1h']):>10} {fmt(c['eph_5m']):>8} "
              f"{fmt(c['input']):>7} {hr:>6}")
        for date in sorted(c["days"]):
            r = c["days"][date]
            dhr = f"{r['hit_rate']:.1%}" if r["hit_rate"] is not None else "-"
            print(f"  {date:<24} {'':>4} {r['calls']:>5} "
                  f"{fmt(r['read']):>11} {fmt(r['creation']):>10} "
                  f"{fmt(r['eph_1h']):>10} {fmt(r['eph_5m']):>8} "
                  f"{fmt(r['input']):>7} {dhr:>6}")
    g = grand
    ghr = f"{g['hit_rate']:.1%}" if g["hit_rate"] is not None else "-"
    print("-" * len(hdr))
    print(f"{'OVERALL':<26} {sum(sess_count.values()):>4} {g['calls']:>5} "
          f"{fmt(g['read']):>11} {fmt(g['creation']):>10} "
          f"{fmt(g['eph_1h']):>10} {fmt(g['eph_5m']):>8} "
          f"{fmt(g['input']):>7} {ghr:>6}")
    if g["eph_1h_share"] is not None:
        print(f"Ephemeral mix overall: 1h {g['eph_1h_share']:.1%} / "
              f"5m {1 - g['eph_1h_share']:.1%} of cache creation "
              f"(governor weights all writes at the 5m price, 1.25x)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
