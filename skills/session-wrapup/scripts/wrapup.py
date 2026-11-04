#!/usr/bin/env python3
"""
session-wrapup — セッション終了時の自動処理スクリプト

機能:
1. Unpushed commit検出
2. Memory consolidation
3. Rule extraction hint
4. Next session prep (pending tasks)
5. Session report output
"""

import subprocess
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Security constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _resolve_workspace(workspace: str) -> str:
    """
    Resolve workspace to its real path (eliminates symlinks and '..').
    Raises ValueError if the resolved path is not an existing directory.
    """
    resolved = os.path.realpath(workspace)
    if not os.path.isdir(resolved):
        raise ValueError(f"Workspace is not a directory: {workspace!r}")
    return resolved


def _safe_join(workspace_real: str, *parts: str) -> str:
    """
    Join *parts to workspace_real and verify the result stays inside workspace_real.
    Raises PermissionError on path-traversal attempts.
    """
    joined = os.path.join(workspace_real, *parts)
    resolved = os.path.realpath(joined)
    # Must equal workspace_real itself or be a direct/nested child
    if resolved != workspace_real and not resolved.startswith(workspace_real + os.sep):
        raise PermissionError(
            f"Path traversal detected: {resolved} escapes workspace"
        )
    return resolved


def _check_file_too_large(path: str, max_bytes: int = MAX_FILE_SIZE) -> bool:
    """Return True if the file exists and its size exceeds max_bytes."""
    try:
        return os.path.getsize(path) > max_bytes
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 1. Git: unpushed / uncommitted detection
# ---------------------------------------------------------------------------

def detect_unpushed_changes(workspace: str) -> dict:
    """
    Run git status --porcelain and git log origin/main..HEAD.
    Returns dict with:
      has_changes: bool
      uncommitted_count: int
      uncommitted_files: list[str]
      unpushed_count: int
      unpushed_commits: list[str]
      error: str (only on failure)
    """
    result = {
        "has_changes": False,
        "uncommitted_count": 0,
        "uncommitted_files": [],
        "unpushed_count": 0,
        "unpushed_commits": [],
    }
    try:
        # Uncommitted changes
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=workspace
        )
        uncommitted = [
            line.strip()
            for line in status.stdout.splitlines()
            if line.strip()
        ]
        result["uncommitted_count"] = len(uncommitted)
        result["uncommitted_files"] = [
            re.sub(r"^.{2}\s*", "", line) for line in uncommitted
        ]

        # Unpushed commits
        log = subprocess.run(
            ["git", "log", "origin/main..HEAD", "--oneline"],
            capture_output=True, text=True, cwd=workspace
        )
        unpushed = [
            line.strip()
            for line in log.stdout.splitlines()
            if line.strip()
        ]
        result["unpushed_count"] = len(unpushed)
        result["unpushed_commits"] = unpushed

        result["has_changes"] = (
            result["uncommitted_count"] > 0 or result["unpushed_count"] > 0
        )

    except Exception as exc:
        result["error"] = str(exc)
        result["has_changes"] = False

    return result


# ---------------------------------------------------------------------------
# 2. Memory consolidation: extract key events from daily md
# ---------------------------------------------------------------------------

def extract_key_events(content: str, max_events: int = 30) -> list[str]:
    """
    Extract key events from a daily memory markdown string.
    Picks up:
      - bullet list items  (lines starting with - or *)
      - section headings   (lines starting with ##)
    Skips blank lines. Returns at most max_events items.
    """
    events = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            events.append(stripped[2:].strip())
        elif stripped.startswith("## "):
            events.append(stripped[3:].strip())
        if len(events) >= max_events:
            break
    return events


# ---------------------------------------------------------------------------
# 3. Summary generation
# ---------------------------------------------------------------------------

def generate_summary(events: list[str], session_date: Optional[date] = None) -> str:
    """
    Produce a human-readable summary string from a list of event strings.
    Always includes the session date.
    """
    if session_date is None:
        session_date = date.today()

    date_str = session_date.strftime("%Y-%m-%d")

    if not events:
        return f"## セッションサマリー ({date_str})\n\n特記事項なし。\n"

    lines = [f"## セッションサマリー ({date_str})\n"]
    for i, event in enumerate(events, 1):
        lines.append(f"  {i}. {event}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 4. Pending task identification
# ---------------------------------------------------------------------------

def identify_pending_tasks(content: str) -> list[dict]:
    """
    Parse AGENT_WORK.md style content and return pending (non-DONE) tasks.
    Each task is a dict with at least:
      title: str
      status: str
    """
    if not content.strip():
        return []

    tasks = []
    in_completed_section = False
    current_task: Optional[dict] = None

    for line in content.splitlines():
        stripped = line.strip()

        # Detect 完了 section boundary
        if re.match(r"^##\s+完了", stripped):
            # Flush current task before entering completed section
            if current_task:
                tasks.append(current_task)
                current_task = None
            in_completed_section = True
            continue

        # Any other ## section resets completed boundary
        if re.match(r"^##\s+", stripped) and not re.match(r"^##\s+完了", stripped):
            in_completed_section = False

        if in_completed_section:
            continue

        # ### Task heading
        m = re.match(r"^###\s+(?:タスク\S*\s*:\s*)?(.+)", stripped)
        if m:
            # Save previous task
            if current_task:
                tasks.append(current_task)
            current_task = {"title": m.group(1).strip(), "status": "UNKNOWN"}
            continue

        # - ステータス: XXX
        if current_task:
            sm = re.match(r"^-\s*ステータス\s*:\s*(.+)", stripped)
            if sm:
                current_task["status"] = sm.group(1).strip()

    # Flush last task
    if current_task:
        tasks.append(current_task)

    return tasks


# ---------------------------------------------------------------------------
# 5. Full wrapup report
# ---------------------------------------------------------------------------

def _read_file_safe(path: str) -> str:
    """Read a file, return empty string on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def generate_wrapup_report(
    workspace: str = "/workspace",
    session_date: Optional[date] = None,
) -> str:
    """
    Generate and return the full session wrapup report as a string.
    All steps are independent — failures in one step do not crash others.
    """
    if session_date is None:
        session_date = date.today()

    date_str = session_date.strftime("%Y-%m-%d")

    # Resolve and validate workspace (eliminates '..' traversal)
    workspace_real = _resolve_workspace(workspace)

    sections: list[str] = []

    # Header
    sections.append(f"# セッション終了レポート — {date_str}\n")
    sections.append(f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    sections.append("---\n")

    # ── 1. Git status ──────────────────────────────────────────────────────
    git_info = detect_unpushed_changes(workspace_real)
    git_section = ["## 📦 Git Status\n"]

    if "error" in git_info:
        git_section.append(f"⚠️  Git確認エラー: {git_info['error']}\n")
    elif not git_info["has_changes"]:
        git_section.append("✅ 未コミット・未プッシュなし\n")
    else:
        if git_info["uncommitted_count"] > 0:
            git_section.append(
                f"⚠️  未コミットファイル: {git_info['uncommitted_count']}件\n"
            )
            for f in git_info["uncommitted_files"][:10]:
                git_section.append(f"  - {f}\n")
        if git_info["unpushed_count"] > 0:
            git_section.append(
                f"⚠️  未プッシュcommit: {git_info['unpushed_count']}件\n"
            )
            for c in git_info["unpushed_commits"][:10]:
                git_section.append(f"  - {c}\n")

    sections.append("".join(git_section))

    # ── 2. Memory consolidation ────────────────────────────────────────────
    daily_path = _safe_join(workspace_real, "memory", f"{date_str}.md")
    rel_daily = os.path.relpath(daily_path, workspace_real)
    mem_section = ["## 🧠 Memory Consolidation\n"]

    if _check_file_too_large(daily_path):
        mem_section.append(f"⚠️  {rel_daily} ファイルが大きすぎます（スキップ）\n")
        daily_content = ""
    else:
        daily_content = _read_file_safe(daily_path)

    if daily_content:
        events = extract_key_events(daily_content)
        summary = generate_summary(events, session_date=session_date)
        mem_section.append(summary + "\n")
    elif not _check_file_too_large(daily_path):
        mem_section.append(f"ℹ️  {rel_daily} が見つかりません。\n")
    sections.append("".join(mem_section))

    # ── 3. Rule extraction hint ────────────────────────────────────────────
    rule_section = ["## 📐 Rule Extraction\n"]
    if daily_content:
        # Heuristic: lines containing ルール, パターン, 教訓, 注意, 必須, 禁止, 絶対
        rule_keywords = re.compile(
            r"(ルール|パターン|教訓|注意|必須|禁止|絶対|べし|してはいけない|学んだ)"
        )
        candidates = [
            line.strip()
            for line in daily_content.splitlines()
            if rule_keywords.search(line)
        ]
        if candidates:
            rule_section.append("以下のルール候補をAGENTS.md/SHARED_RULES.mdへの追記を検討:\n")
            for c in candidates[:10]:
                rule_section.append(f"  > {c}\n")
        else:
            rule_section.append("ルール候補なし。\n")
    else:
        rule_section.append("ℹ️  日次メモリファイルなし。スキップ。\n")
    sections.append("".join(rule_section))

    # ── 4. Next session prep ───────────────────────────────────────────────
    work_path = _safe_join(workspace_real, "memory", "AGENT_WORK.md")
    rel_work = os.path.relpath(work_path, workspace_real)
    prep_section = ["## 🔜 Next Session Prep\n"]

    if _check_file_too_large(work_path):
        prep_section.append(f"⚠️  {rel_work} ファイルが大きすぎます（スキップ）\n")
    else:
        work_content = _read_file_safe(work_path)
        if work_content:
            pending = identify_pending_tasks(work_content)
            if pending:
                prep_section.append(f"未完了タスク: {len(pending)}件\n")
                for task in pending:
                    status = task.get("status", "UNKNOWN")
                    title = task.get("title", "(無題)")
                    prep_section.append(f"  [{status}] {title}\n")
            else:
                prep_section.append("✅ 未完了タスクなし\n")
        else:
            prep_section.append(f"ℹ️  {rel_work} が見つかりません。\n")
    sections.append("".join(prep_section))

    # ── Footer ─────────────────────────────────────────────────────────────
    sections.append("---\n")
    sections.append("_次のセッションで `/wrapup` を実行すれば再生成できます。_\n")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Session wrapup report")
    parser.add_argument(
        "--workspace", default="/workspace", help="Workspace root path"
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Session date (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()

    session_date = date.today()
    if args.date:
        session_date = date.fromisoformat(args.date)

    report = generate_wrapup_report(workspace=args.workspace, session_date=session_date)
    print(report)
