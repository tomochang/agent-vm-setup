#!/usr/bin/env python3
"""C4 usage meter: Claude Code CLI usage from its session logs (skipbit's method).

Reads ~/.claude/projects/*/*.jsonl. Assistant messages carry
message.id / message.model / message.usage {input_tokens, output_tokens,
cache_read_input_tokens, cache_creation_input_tokens}. The same API response
is written to the log multiple times as streamed partial records, with usage
values cumulative, so records are deduped by message.id keeping the record
whose four token fields sum to the maximum (skipbit's method).

Column definitions for usage.csv:
  date                          JST (Asia/Tokyo) date of the kept record's timestamp
  calls                         deduped API calls = distinct message.id count
  messages                      raw usage-bearing assistant lines before dedupe
                                (streamed partials included; messages - calls
                                shows how much duplicate/partial inflation was
                                removed; attributed to the deduped message's date)
  input_tokens                  sum over deduped messages
  output_tokens                 ditto
  cache_read_input_tokens       ditto
  cache_creation_input_tokens   ditto
  total_tokens                  sum of the four token columns

Codex logs (~/.codex/sessions/**/*.jsonl) DO contain usage numbers
(payload.type == "token_count", payload.info.total_token_usage, cumulative
per session). They are parsed separately (final cumulative snapshot per
session file) and reported in coverage.md only -- NOT merged into
usage.csv, because Codex's cached_input_tokens is a subset of its
input_tokens whereas Claude's cache_read is separate from input_tokens,
so adding them would double-count / mix semantics.

Coverage gap (also stated in coverage.md): Muse (chat / cron) tokens are
NOT in these logs. Missing there != zero usage.

Never crashes on bad input: malformed JSON lines, lines without usage,
usage records without a usable timestamp or message.id are counted as
skips and reported in coverage.md.

Usage:
  python3 usage_report.py [--days N] [--out DIR]
                          [--projects DIR] [--codex DIR]
Default --out: ~/workspace/overnight-improvements-20261102/metrics
Python 3 stdlib only.
"""
import argparse
import csv
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except Exception:  # pragma: no cover - zoneinfo data missing
    JST = timezone(timedelta(hours=9), "JST")

DEFAULT_OUT = os.path.expanduser(
    "~/workspace/overnight-improvements-20261102/metrics")
TOKEN_FIELDS = ("input_tokens", "output_tokens",
                "cache_read_input_tokens", "cache_creation_input_tokens")
CSV_FIELDS = ["date", "calls", "messages", "input_tokens", "output_tokens",
              "cache_read_input_tokens", "cache_creation_input_tokens",
              "total_tokens"]


def parse_ts(raw):
    """ISO-8601 timestamp -> aware datetime, or None."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def jst_date(raw):
    dt = parse_ts(raw)
    return dt.astimezone(JST).date().isoformat() if dt else None


def tok(usage, field):
    v = usage.get(field, 0)
    return v if isinstance(v, int) and v >= 0 else 0


def scan_claude(projects_dir):
    """Return (per_day, stats, per_file). per_day: date -> counters dict."""
    files = sorted(glob.glob(os.path.join(projects_dir, "*", "*.jsonl")))
    best = {}  # message.id -> (total, ts_raw, usage tuple)
    stats = dict(files=0, lines=0, malformed=0, no_usage=0,
                 no_id=0, no_timestamp=0, raw_usage_lines=0)
    per_file = []
    for path in files:
        stats["files"] += 1
        f_lines = f_bad = f_usage = 0
        try:
            fh = open(path, "r", encoding="utf-8", errors="replace")
        except OSError as e:
            per_file.append((path, 0, 0, 0, "unreadable: %s" % e))
            continue
        with fh:
            for line in fh:
                f_lines += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, RecursionError):
                    f_bad += 1
                    continue
                if not isinstance(obj, dict):
                    f_bad += 1
                    continue
                msg = obj.get("message")
                if not isinstance(msg, dict) or not isinstance(
                        msg.get("usage"), dict):
                    stats["no_usage"] += 1
                    continue
                usage = msg["usage"]
                mid = msg.get("id")
                if not mid:
                    stats["no_id"] += 1
                    continue
                if jst_date(obj.get("timestamp")) is None:
                    stats["no_timestamp"] += 1
                    continue
                f_usage += 1
                vals = tuple(tok(usage, f) for f in TOKEN_FIELDS)
                total = sum(vals)
                cur = best.get(mid)
                # Keep the max-total (cumulative-final) record; tie -> latest ts.
                # [3] counts raw lines for this id, so `messages` can be
                # attributed to the deduped message's (kept record's) date
                # even when a streamed partial falls on the previous JST day.
                if cur is None or total > cur[0] or (
                        total == cur[0] and str(obj.get("timestamp")) > cur[1]):
                    best[mid] = (total, str(obj.get("timestamp")), vals,
                                 (cur[3] if cur else 0) + 1)
                else:
                    best[mid] = (cur[0], cur[1], cur[2], cur[3] + 1)
        stats["lines"] += f_lines
        stats["malformed"] += f_bad
        stats["raw_usage_lines"] += f_usage
        per_file.append((path, f_lines, f_bad, f_usage, ""))
    # Attribute each deduped message (and its raw-line count) to the JST
    # date of its kept record.
    per_day = defaultdict(lambda: dict(calls=0, messages=0, **{
        f: 0 for f in TOKEN_FIELDS}))
    for _total, ts_raw, vals, raw_n in best.values():
        d = jst_date(ts_raw)
        row = per_day[d]
        row["calls"] += 1
        row["messages"] += raw_n
        for f, v in zip(TOKEN_FIELDS, vals):
            row[f] += v
    return per_day, stats, per_file, best


def scan_codex(codex_dir):
    """Parse Codex session logs. Returns (present, per_day, notes).

    Format (verified 2026-11-02): ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl,
    lines are {timestamp, type:"event_msg", payload:{type:"token_count",
    info:{total_token_usage:{...}, last_token_usage:{...}}}}.
    total_token_usage is cumulative per session, so the per-file FINAL
    snapshot is the session total (summing snapshots would double-count).
    """
    files = sorted(glob.glob(os.path.join(codex_dir, "sessions", "**",
                                           "*.jsonl"), recursive=True))
    notes = []
    per_day = defaultdict(lambda: dict(input_tokens=0, output_tokens=0,
                                       cached_input_tokens=0, sessions=0))
    if not files:
        notes.append("No Codex session jsonl files found under %s "
                     "(sessions/**/*.jsonl)." % codex_dir)
        return False, per_day, notes
    parsed = 0
    for path in files:
        final = None
        final_ts = None
        try:
            fh = open(path, "r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except (ValueError, RecursionError):
                    continue
                if not isinstance(obj, dict):
                    continue
                payload = obj.get("payload")
                if not isinstance(payload, dict) or \
                        payload.get("type") != "token_count":
                    continue
                info = payload.get("info") or {}
                tot = info.get("total_token_usage")
                if isinstance(tot, dict) and tot:
                    final, final_ts = tot, obj.get("timestamp")
        if final is not None:
            parsed += 1
            d = jst_date(final_ts) or "unknown-date"
            row = per_day[d]
            row["sessions"] += 1
            row["input_tokens"] += tok(final, "input_tokens")
            row["output_tokens"] += tok(final, "output_tokens")
            row["cached_input_tokens"] += tok(final, "cached_input_tokens")
    notes.append(
        "Codex logs present: %d rollout jsonl file(s) under %s/sessions; "
        "%d contained token_count usage. Format DOES clearly contain usage "
        "numbers (payload.type=='token_count', info.total_token_usage "
        "cumulative per session + info.last_token_usage per call), so they "
        "were parsed using each file's final cumulative snapshot. They are "
        "reported in the Codex table below ONLY and are NOT merged into "
        "usage.csv: Codex cached_input_tokens is a subset of input_tokens, "
        "while Claude cache_read_input_tokens is separate from "
        "input_tokens -- merging would double-count." % (
            len(files), codex_dir, parsed))
    return True, per_day, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=None,
                    help="only include the last N JST days (incl. today)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output directory")
    ap.add_argument("--projects", default=os.path.expanduser(
        "~/.claude/projects"), help="Claude projects dir (for fixtures)")
    ap.add_argument("--codex", default=os.path.expanduser("~/.codex"),
                    help="Codex home dir")
    args = ap.parse_args(argv)

    per_day, stats, per_file, _best = scan_claude(args.projects)

    if args.days is not None and args.days > 0:
        today_jst = datetime.now(JST).date()
        cutoff = (today_jst - timedelta(days=args.days - 1)).isoformat()
        per_day = {d: r for d, r in per_day.items() if d >= cutoff}

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "usage.csv")

    # Append/update: keep existing rows for dates not recomputed now.
    merged = {}
    if os.path.exists(csv_path):
        try:
            with open(csv_path, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    if row.get("date"):
                        merged[row["date"]] = row
        except OSError:
            pass
    for d, r in per_day.items():
        merged[d] = {
            "date": d, "calls": r["calls"], "messages": r["messages"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "cache_read_input_tokens": r["cache_read_input_tokens"],
            "cache_creation_input_tokens": r["cache_creation_input_tokens"],
            "total_tokens": sum(r[f] for f in TOKEN_FIELDS),
        }
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        w.writeheader()
        for d in sorted(merged):
            w.writerow({k: merged[d].get(k, 0) for k in CSV_FIELDS})

    codex_present, codex_day, codex_notes = scan_codex(args.codex)

    cov = []
    cov.append("# Usage coverage — usage_report.py")
    cov.append("")
    cov.append("Generated: %s (Asia/Tokyo)" % datetime.now(JST).strftime(
        "%Y-%m-%d %H:%M:%S %Z"))
    cov.append("Source: `%s/*/*.jsonl`" % args.projects)
    if args.days:
        cov.append("Window: last %d JST day(s) only." % args.days)
    cov.append("")
    cov.append("## Coverage gap (read this first)")
    cov.append("")
    cov.append("**Muse (chat / cron) tokens are NOT covered by these "
               "logs.** `~/.claude/projects` only records local Claude Code "
               "CLI sessions on this machine. Muse-side chat and cron "
               "usage does not appear here at all: a day missing from "
               "usage.csv, or a low number, means 'not measured', NOT "
               "zero usage.")
    cov.append("")
    cov.append("## Claude Code logs")
    cov.append("")
    cov.append("- Files scanned: %d" % stats["files"])
    cov.append("- Total lines read: %d" % stats["lines"])
    cov.append("- Raw usage-bearing assistant lines: %d"
               % stats["raw_usage_lines"])
    cov.append("- Unparsable / malformed JSON lines (skipped): %d"
               % stats["malformed"])
    cov.append("- Parsed lines without message.usage (skipped): %d"
               % stats["no_usage"])
    cov.append("- Usage lines without message.id (skipped): %d"
               % stats["no_id"])
    cov.append("- Usage lines without a usable timestamp (skipped): %d"
               % stats["no_timestamp"])
    cov.append("- Deduped API calls (distinct message.id): %d"
               % sum(r["calls"] for r in per_day.values()))
    cov.append("")
    cov.append("Days covered: %s" % (
        ", ".join(sorted(per_day)) if per_day else "(none)"))
    cov.append("")
    cov.append("| file | lines | malformed | usage lines | note |")
    cov.append("|---|---|---|---|---|")
    for path, n, bad, use, note in per_file:
        cov.append("| %s | %d | %d | %d | %s |" % (path, n, bad, use, note))
    cov.append("")
    cov.append("Dedupe rule (skipbit): group by message.id, keep the record "
               "whose input+output+cache_read+cache_creation sum is "
               "largest (usage is cumulative across streamed partials). "
               "A deduped message is dated by its kept record's timestamp, "
               "converted UTC -> Asia/Tokyo.")
    cov.append("")
    cov.append("## Codex logs (~/.codex)")
    cov.append("")
    for n in codex_notes:
        cov.append("- " + n)
    if codex_present and codex_day:
        cov.append("")
        cov.append("| date (JST) | sessions | input_tokens | "
                   "output_tokens | cached_input_tokens (subset of input) |")
        cov.append("|---|---|---|---|---|")
        for d in sorted(codex_day):
            r = codex_day[d]
            cov.append("| %s | %d | %d | %d | %d |" % (
                d, r["sessions"], r["input_tokens"], r["output_tokens"],
                r["cached_input_tokens"]))
    cov.append("")
    with open(os.path.join(args.out, "coverage.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(cov))

    print("wrote %s (%d day rows) and coverage.md" % (
        csv_path, len(merged)))
    print("claude: files=%d lines=%d malformed=%d calls(deduped)=%d "
          "raw_usage_lines=%d" % (
              stats["files"], stats["lines"], stats["malformed"],
              sum(r["calls"] for r in per_day.values()),
              stats["raw_usage_lines"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
