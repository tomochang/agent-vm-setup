#!/usr/bin/env python3
"""spend_governor — persistent spend accounting + kill-switch verdict
for the resident agent's own automated work.

Pattern: the "leash" spend governor (research/mofu-vs-vanilla,
sources/leash-spend-governor.md): an agent's in-memory step/budget
counter resets on restart, so the accounting must be derived from a
durable ledger and checked before heavy work runs, not after the fact.

What it measures: local Claude Code CLI usage, from the same source
usage_report.py meters — the session logs under ~/.claude/projects
(skipbit dedupe by message.id). Daily spend is expressed in weighted
units: input x1, cache read x0.1, output x5, and cache writes split
by TTL — ephemeral_1h x2.0 (the real 1-hour write price),
ephemeral_5m x1.25. Write tokens with no ephemeral split fall back
to x1.25 and are counted (fallbacks are reported in the output JSON;
at the 2026-11-03 correction the count was 0 of 263 usage records,
and the measured mix on this VM was 1h 100% / 5m 0%). The split is
parsed with cache_caller_report.py's session scan, reused because
usage_report.py's per-day aggregate does not retain it.

Unit correction (approved by the operator 2026-11-03): writes were
originally weighted flat at x1.25 — the 5-minute price — while every
measured write was a 1-hour write costing 2x base input, so the
governor understated the write component by ~37%. The ruler was
fixed and the cap re-derived in the new unit under the same rule
(baseline daily average x 1.5); see spend-governor.json for the
old -> new derivation.

Persistence (why a restart cannot reset it): nothing is counted in
process memory or in /tmp. Every run re-derives the numbers from the
jsonl session logs, which live under the home directory — the only tree that
survives this VM's replacements. Restart the VM, the tool, or the
heartbeat and the same logs give the same totals; the budget cannot
silently reopen. The cap itself lives in spend-governor.json next to
this script (also under the home directory).

Coverage caveat (inherited from usage_report.py): Muse chat / cron
tokens are NOT in these logs, and neither is the Mac Foreman's usage.
The governor therefore governs the metered slice — VM-local Claude
Code CLI delegation — not the resident agent's total platform spend. A day missing
from the logs means "not measured", never "zero".

Verdicts (one JSON line on stdout):
  ok        today < 80% of the daily cap
  warn      today >= 80% of the cap (exit 1)
  stop      today >= 100% of the cap (exit 1)
  uncapped  no cap set in spend-governor.json (exit 0); today and the
            rolling average are still reported

The cap was set by the operator's trial rule (2026-11-03): baseline daily
average x 1.5, where the baseline is the mean of the complete measured
days in the usage history at setup time. The derivation is recorded in
spend-governor.json; as more history accrues, re-derive rather than
guess.

INTEGRATION CONTRACT (step one — contract only, spenders not yet
rewired): automated spenders consult this verdict BEFORE starting
heavy work and honour it:
  - todo crons (todo-auto-advance, beeper-todo-sync) before delegating
    to Claude Code / Codex CLI workers;
  - research spawns and any multi-agent fan-out launched from cron or
    heartbeat contexts.
On "stop": do not start new heavy CLI work; fall back to inline/light
work and note the verdict in the run log. On "warn": proceed only with
work that is already determined, prefer the lightest sufficient path.
Interactive work the operator asks for directly is never blocked by this
verdict — it governs automated spend, not his requests.

Usage: spend_governor.py [--projects DIR] [--config PATH]
Exit 0 for ok/uncapped, 1 for warn/stop. Python 3 stdlib only.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "usage-report"))
from usage_report import scan_claude, JST  # noqa: E402
import cache_caller_report as ccr  # noqa: E402

WEIGHTS = {"input_tokens": 1.0, "cache_read_input_tokens": 0.1,
           "output_tokens": 5.0}
WRITE_WEIGHT_1H = 2.0    # ephemeral_1h write: 2x base input price
WRITE_WEIGHT_5M = 1.25   # ephemeral_5m write; also the unsplit fallback
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "spend-governor.json")
WARN_FRACTION = 0.8
COVERAGE = ("local Claude Code CLI logs only (~/.claude/projects); "
            "Muse chat/cron and Mac Foreman usage are not metered")
UNIT = ("weighted units: input x1, cache read x0.1, output x5, "
        "cache write ephemeral_1h x2.0 / ephemeral_5m x1.25 "
        "(unsplit writes x1.25, counted as fallbacks)")


def ephemeral_by_day(projects_dir):
    """{JST date: {eph_1h, eph_5m}} plus fallback stats, from
    cache_caller_report's session scan (the split usage_report.py's
    aggregate drops). A deduped message counts as a fallback when it
    has cache-creation tokens not covered by the ephemeral split."""
    by_day = {}
    fb_records = fb_tokens = 0
    for sess in ccr.scan_sessions(projects_dir).values():
        for rec in sess["messages"].values():
            row = by_day.setdefault(rec["date"], {"eph_1h": 0, "eph_5m": 0})
            row["eph_1h"] += rec["eph_1h"]
            row["eph_5m"] += rec["eph_5m"]
            unsplit = rec["creation"] - rec["eph_1h"] - rec["eph_5m"]
            if rec["creation"] > 0 and unsplit > 0:
                fb_records += 1
                fb_tokens += unsplit
    return by_day, fb_records, fb_tokens


def weighted(row, eph_row=None):
    units = sum(row.get(f, 0) * w for f, w in WEIGHTS.items())
    creation = row.get("cache_creation_input_tokens", 0)
    eph = eph_row or {}
    e1h, e5m = eph.get("eph_1h", 0), eph.get("eph_5m", 0)
    unsplit = max(0, creation - e1h - e5m)
    return (units + e1h * WRITE_WEIGHT_1H + e5m * WRITE_WEIGHT_5M
            + unsplit * WRITE_WEIGHT_5M)


def load_config(path):
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projects", default=os.path.expanduser(
        "~/.claude/projects"), help="Claude projects dir")
    ap.add_argument("--config", default=DEFAULT_CONFIG,
                    help="cap config JSON")
    args = ap.parse_args(argv)

    per_day, _stats, _per_file, _best = scan_claude(args.projects)
    eph_by_day, fb_records, fb_tokens = ephemeral_by_day(args.projects)
    today = datetime.now(JST).date()
    today_s = today.isoformat()
    today_units = round(weighted(per_day.get(today_s, {}),
                                 eph_by_day.get(today_s)))

    window_start = (today - timedelta(days=7)).isoformat()
    complete = [weighted(r, eph_by_day.get(d))
                for d, r in sorted(per_day.items())
                if window_start <= d < today_s and r.get("calls", 0) > 0]
    rolling_avg = round(sum(complete) / len(complete)) if complete else None

    cfg = load_config(args.config)
    cap = cfg.get("daily_cap_units")
    warn_fraction = cfg.get("warn_fraction", WARN_FRACTION)
    if not isinstance(cap, (int, float)) or cap <= 0:
        verdict, pct = "uncapped", None
    else:
        pct = round(today_units / cap, 3)
        if today_units >= cap:
            verdict = "stop"
        elif today_units >= warn_fraction * cap:
            verdict = "warn"
        else:
            verdict = "ok"

    print(json.dumps({
        "tool": "spend_governor",
        "date": today_s,
        "verdict": verdict,
        "today_units": today_units,
        "cap_units": cap,
        "pct_of_cap": pct,
        "rolling_avg_units": rolling_avg,
        "rolling_days": len(complete),
        "unit": UNIT,
        "write_fallback_records": fb_records,
        "write_fallback_tokens": fb_tokens,
        "coverage": COVERAGE,
    }, ensure_ascii=False))
    return 1 if verdict in ("warn", "stop") else 0


if __name__ == "__main__":
    sys.exit(main())
