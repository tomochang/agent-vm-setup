#!/usr/bin/env python3
"""improvement_scout — cheap signal collector for the weekly improvement scout.

Gathers, deterministically and read-only, the raw material from which the
scout cron drafts improvement proposals. No judgment lives here; the cron's
agent pass applies the filter (existing venues only, payoff named, not
already decided) and presents at most 3 proposals.

Signals:
  failure_ledger    signatures with occurrences and no recorded mechanism
                    (count 1 = mechanism candidate, >=2 = unresolved repeat)
  stale_worktrees   records worktrees whose branch tip is fully contained in
                    origin/main (landed leftovers, safe to remove)
  handoff_branches  factory-handoff remote task/* branches already merged
                    into that repo's main (cleanup candidates)
  aging_agent_items agent-todo items in a waiting_* state whose `updated`
                    date is >= AGING_DAYS old (blocker may have cleared)
  stale_todo_rows   todo (records origin/main) entries that look
                    finished or overdue: schedule-table rows whose last
                    date has passed, and checkbox items whose stated
                    deadline passed with no later date in the item (i.e.
                    not visibly rescheduled). FLAGS ONLY — the scout's
                    agent pass must verify each flag against Beeper,
                    Google Calendar and Gmail before proposing any move
                    or fix (the operator's rule, 2026-11-03: todo text alone
                    never settles an outcome)

Prints one JSON object. Always exits 0; a failed source reports null.
"""

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

HOME = os.path.expanduser("~")
LEDGER = os.environ.get("FAILURE_LEDGER", os.path.join(HOME, "workspace/tools/failure-ledger.jsonl"))
RECORDS = os.environ.get("RECORDS_DIR", os.path.join(HOME, "workspace/records"))
HANDOFF = os.environ.get("HANDOFF_DIR", os.path.join(HOME, "workspace/factory-handoff"))
ITEMS_DIR = os.environ.get("ITEMS_DIR", os.path.join(HOME, "workspace/your_files/agent-todo-items"))
AGING_DAYS = 5


def failure_ledger():
    counts, mechanized = {}, set()
    try:
        with open(LEDGER, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("kind") == "occurrence":
                    counts[row["signature"]] = counts.get(row["signature"], 0) + 1
                elif row.get("kind") == "mechanism":
                    mechanized.add(row["signature"])
    except OSError:
        return None
    return [
        {"signature": s, "occurrences": n,
         "state": "unresolved-repeat" if n >= 2 else "candidate"}
        for s, n in sorted(counts.items()) if s not in mechanized
    ]


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args],
                       capture_output=True, text=True, timeout=30)
    return r.stdout if r.returncode == 0 else None


def stale_worktrees():
    out = git(RECORDS, "worktree", "list", "--porcelain")
    if out is None:
        return None
    stale, current = [], None
    entries = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            current = {"path": line[9:]}
            entries.append(current)
        elif line.startswith("branch ") and current is not None:
            current["branch"] = line[7:].replace("refs/heads/", "")
    for e in entries:
        branch = e.get("branch")
        if not branch or e["path"] == RECORDS:
            continue
        r = subprocess.run(
            ["git", "-C", RECORDS, "merge-base", "--is-ancestor",
             f"refs/heads/{branch}", "origin/main"],
            capture_output=True, timeout=30)
        if r.returncode == 0:
            stale.append({"worktree": e["path"], "branch": branch})
    return stale


def handoff_branches():
    out = git(HANDOFF, "branch", "-r", "--merged", "origin/main")
    if out is None:
        return None
    return [ln.strip().replace("origin/", "")
            for ln in out.splitlines()
            if ln.strip().startswith("origin/task/")]


def aging_agent_items():
    try:
        names = os.listdir(ITEMS_DIR) if os.path.isdir(ITEMS_DIR) else []
    except OSError:
        return None
    today = date.today()
    aging = []
    for name in sorted(names):
        if not name.endswith(".md"):
            continue
        try:
            with open(os.path.join(ITEMS_DIR, name), encoding="utf-8") as f:
                head = f.read(1500)
        except OSError:
            continue
        fm = {}
        for line in head.splitlines():
            if ":" in line and not line.startswith("#"):
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
        status, updated = fm.get("status", ""), fm.get("updated", "")
        if not status.startswith("waiting") or not updated:
            continue
        try:
            upd = datetime.strptime(updated[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        age = (today - upd).days
        if age >= AGING_DAYS:
            aging.append({"id": fm.get("id", name), "status": status,
                          "updated": updated[:10], "age_days": age,
                          "blocked": fm.get("blocked", "")})
    return aging


def _todo_text():
    override = os.environ.get("TODO_FILE")
    if override:
        try:
            with open(override, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None
    git(RECORDS, "fetch", "origin", "-q")
    return git(RECORDS, "show", "origin/main:private/todo.md")


def _md_date(month, day, today):
    year = today.year + (1 if today.month == 12 and month == 1 else 0)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def stale_todo_rows():
    text = _todo_text()
    if text is None:
        return None
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    flags = []
    # Schedule-table rows: stale once the LAST date in the date cell passed.
    in_table = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_table = line.startswith("## 今後の確定予定")
            continue
        if not in_table or not line.startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) < 3:
            continue
        date_cell, title = cells[1].strip(), cells[2].strip()
        if not date_cell or date_cell.startswith("日付") or "未定" in date_cell:
            continue
        dates = [d for d in (_md_date(int(m), int(d), today)
                             for m, d in re.findall(r"(\d{1,2})/(\d{1,2})", date_cell))
                 if d is not None]
        if dates and max(dates) < today:
            flags.append({"kind": "schedule-row", "title": title[:60],
                          "last_date": max(dates).isoformat()})
    # Checkbox items: stated deadline passed and no later date in the block
    # (a later date means it was visibly rescheduled, e.g. the 個人番号 item).
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("- [ ]"):
            continue
        block = "\n".join(lines[i:i + 3])
        dm = re.search(r"期限:\s*(?:当初)?\s*(20\d\d)-(\d\d)-(\d\d)", block)
        if not dm:
            continue
        deadline = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
        if deadline >= today:
            continue
        later = [date(int(y), int(m), int(d))
                 for y, m, d in re.findall(r"(20\d\d)-(\d\d)-(\d\d)", block)]
        if any(d >= today for d in later if d != deadline):
            continue
        tm = re.search(r"\*\*(.+?)\*\*", line)
        flags.append({"kind": "item", "title": (tm.group(1) if tm else line[6:])[:60],
                      "deadline": deadline.isoformat()})
    return flags


def main():
    signals = {
        "failure_ledger": failure_ledger(),
        "stale_worktrees": stale_worktrees(),
        "handoff_branches": handoff_branches(),
        "aging_agent_items": aging_agent_items(),
        "stale_todo_rows": stale_todo_rows(),
    }
    print(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "counts": {k: (len(v) if isinstance(v, list) else None)
                   for k, v in signals.items()},
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
