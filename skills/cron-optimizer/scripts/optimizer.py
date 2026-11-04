"""
cron-optimizer — cronジョブの棚卸し・最適化スクリプト

Usage:
    python3 scripts/optimizer.py [--check-scripts] [--openclaw-config PATH] [--dry-run]

安全ポリシー: cronの変更は提案のみ。自動変更しない。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CronJob:
    """Represents a single line in a crontab file."""

    raw_line: str
    is_comment: bool = False
    is_commented_cron: bool = False  # e.g. "# 0 5 * * * /path/cmd"

    minute: str = ""
    hour: str = ""
    day_of_month: str = ""
    month: str = ""
    day_of_week: str = ""
    command: str = ""

    @property
    def schedule(self) -> str:
        return f"{self.minute} {self.hour} {self.day_of_month} {self.month} {self.day_of_week}"

    @property
    def schedule_key(self) -> str:
        """Normalised key used to group jobs by time slot."""
        return f"{self.minute} {self.hour}"

    def __repr__(self) -> str:
        if self.is_comment:
            return f"<CronJob comment: {self.raw_line.strip()!r}>"
        return f"<CronJob [{self.schedule}] {self.command!r}>"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches a standard 5-field cron expression followed by a command
_CRON_RE = re.compile(
    r"^(?P<min>\S+)\s+(?P<hour>\S+)\s+(?P<dom>\S+)\s+(?P<mon>\S+)\s+(?P<dow>\S+)\s+(?P<cmd>.+)$"
)

# Matches a commented-out cron line: "# <5fields> <command>"
_COMMENTED_CRON_RE = re.compile(
    r"^#\s*(?P<min>[\d*/,\-]+)\s+(?P<hour>[\d*/,\-]+)\s+(?P<dom>[\d*/,\-]+)\s+"
    r"(?P<mon>[\d*/,\-]+)\s+(?P<dow>[\d*/,\-]+)\s+(?P<cmd>.+)$"
)

# Known "no crontab" messages from various distros
_NO_CRONTAB_RE = re.compile(r"^no crontab for ", re.IGNORECASE)


def parse_crontab(text: str) -> list[CronJob]:
    """Parse raw crontab text into a list of CronJob objects."""
    jobs: list[CronJob] = []
    for line in text.splitlines():
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Skip "no crontab for …" messages
        if _NO_CRONTAB_RE.match(stripped):
            continue

        if stripped.startswith("#"):
            # Try to detect commented-out cron entries
            m = _COMMENTED_CRON_RE.match(stripped)
            if m:
                job = CronJob(
                    raw_line=line,
                    is_comment=True,
                    is_commented_cron=True,
                    minute=m.group("min"),
                    hour=m.group("hour"),
                    day_of_month=m.group("dom"),
                    month=m.group("mon"),
                    day_of_week=m.group("dow"),
                    command=m.group("cmd").strip(),
                )
            else:
                job = CronJob(raw_line=line, is_comment=True)
            jobs.append(job)
            continue

        m = _CRON_RE.match(stripped)
        if m:
            job = CronJob(
                raw_line=line,
                is_comment=False,
                minute=m.group("min"),
                hour=m.group("hour"),
                day_of_month=m.group("dom"),
                month=m.group("mon"),
                day_of_week=m.group("dow"),
                command=m.group("cmd").strip(),
            )
            jobs.append(job)
        # Lines that don't match (env vars, @reboot, etc.) are silently skipped
        # for now — extend as needed.

    return jobs


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def detect_duplicates(jobs: list[CronJob]) -> list[dict[str, Any]]:
    """Return groups of active jobs that share the exact same command."""
    active = [j for j in jobs if not j.is_comment]
    grouped: dict[str, list[CronJob]] = defaultdict(list)
    for job in active:
        grouped[job.command].append(job)

    result = []
    for cmd, occurrences in grouped.items():
        if len(occurrences) > 1:
            result.append({"command": cmd, "occurrences": occurrences})
    return result


def detect_schedule_conflicts(
    jobs: list[CronJob], threshold: int = 4
) -> list[dict[str, Any]]:
    """Return groups of active jobs whose schedule_key appears >= threshold times."""
    active = [j for j in jobs if not j.is_comment]
    grouped: dict[str, list[CronJob]] = defaultdict(list)
    for job in active:
        grouped[job.schedule_key].append(job)

    result = []
    for key, group in grouped.items():
        if len(group) >= threshold:
            result.append({"schedule_key": key, "jobs": group})
    return result


def detect_commented_jobs(jobs: list[CronJob]) -> list[dict[str, Any]]:
    """Return jobs that are commented-out cron entries (not plain comments)."""
    return [
        {"line": j.raw_line.strip(), "command": j.command, "job": j}
        for j in jobs
        if j.is_commented_cron
    ]


def _extract_script_paths(command: str) -> list[str]:
    """
    Extract absolute-path arguments from a command string.

    Examples:
        "/usr/bin/python3 /home/user/script.py"  → ["/home/user/script.py"]
        "/scripts/backup.sh"                      → ["/scripts/backup.sh"]
        "echo hello"                              → []
    """
    parts = command.split()
    paths: list[str] = []

    interpreters = {"/usr/bin/python3", "/usr/bin/python", "python3", "python",
                    "/bin/bash", "/usr/bin/bash", "bash", "/bin/sh", "sh",
                    "/usr/bin/perl", "perl", "/usr/bin/ruby", "ruby"}

    for i, part in enumerate(parts):
        if not part.startswith("/"):
            continue
        # If it looks like an interpreter and there's a next arg, skip it
        if part in interpreters or os.path.basename(part) in {"python3", "python",
                                                               "bash", "sh", "perl", "ruby"}:
            # the next absolute-path argument is the actual script
            continue
        paths.append(part)

    # Also pick up the first absolute-path arg after an interpreter
    for i, part in enumerate(parts):
        base = os.path.basename(part)
        if base in {"python3", "python", "bash", "sh", "perl", "ruby"} or part in interpreters:
            # look ahead for an absolute path
            for j in range(i + 1, len(parts)):
                if parts[j].startswith("/"):
                    if parts[j] not in paths:
                        paths.append(parts[j])
                    break

    return paths


def detect_missing_scripts(jobs: list[CronJob]) -> list[dict[str, Any]]:
    """Return active jobs whose referenced scripts do not exist on disk."""
    active = [j for j in jobs if not j.is_comment]
    missing = []
    for job in active:
        scripts = _extract_script_paths(job.command)
        for script in scripts:
            if not os.path.exists(script):
                missing.append({"job": job, "script": script, "command": job.command})
    return missing


# ---------------------------------------------------------------------------
# OpenClaw config parsing
# ---------------------------------------------------------------------------

def parse_openclaw_cron(config_path: str) -> dict[str, Any] | None:
    """
    Parse an openclaw.json file and return its cron section.

    Returns None if the file doesn't exist.
    Returns {"jobs": [...]} (empty list if no "cron" key).
    """
    if not os.path.exists(config_path):
        return None

    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            return {"jobs": [], "parse_error": str(exc)}

    cron_jobs = data.get("cron", [])
    return {"jobs": cron_jobs}


def detect_openclaw_issues(openclaw_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Detect issues in OpenClaw cron configuration."""
    if openclaw_result is None:
        return []

    issues = []
    for job in openclaw_result.get("jobs", []):
        if not job.get("enabled", True):
            issues.append({"type": "disabled", "job": job})
    return issues


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_optimization_report(
    duplicates: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    commented: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    openclaw_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compile all findings into a structured report with suggestions."""
    suggestions: list[str] = []

    if duplicates:
        for dup in duplicates:
            suggestions.append(
                f"重複削除: '{dup['command']}' が {len(dup['occurrences'])} 回登録されています。"
                " 1つを残して削除してください。"
            )

    if conflicts:
        for conflict in conflicts:
            suggestions.append(
                f"スケジュール集中: '{conflict['schedule_key']}' に {len(conflict['jobs'])} 個のジョブが集中しています。"
                " スケジュールを分散させることを検討してください。"
            )

    if commented:
        for c in commented:
            suggestions.append(
                f"コメントアウト済みジョブ: '{c['command']}' — 不要なら削除してください。"
            )

    if missing:
        for m in missing:
            suggestions.append(
                f"スクリプト不在: '{m['script']}' が見つかりません。ジョブを確認してください。"
            )

    if openclaw_issues:
        for issue in openclaw_issues:
            if issue["type"] == "disabled":
                task = issue["job"].get("task", "unknown")
                suggestions.append(
                    f"OpenClaw無効ジョブ: '{task}' が無効化されています。不要なら設定から削除してください。"
                )

    total = len(duplicates) + len(conflicts) + len(commented) + len(missing) + len(openclaw_issues)

    return {
        "issues": duplicates + conflicts + commented + missing + openclaw_issues,
        "duplicates": duplicates,
        "schedule_conflicts": conflicts,
        "commented_jobs": commented,
        "missing_scripts": missing,
        "openclaw_issues": openclaw_issues,
        "suggestions": suggestions,
        "total_issues": total,
    }


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

def _get_crontab_text() -> str:
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
    except FileNotFoundError:
        print("[警告] crontab コマンドが見つかりません。", file=sys.stderr)
        return ""
    except subprocess.TimeoutExpired:
        print("[警告] crontab -l がタイムアウトしました。", file=sys.stderr)
        return ""


def _print_report(report: dict[str, Any], dry_run: bool) -> None:
    print("=" * 60)
    print("cron-optimizer レポート")
    print("=" * 60)

    total = report["total_issues"]
    if total == 0:
        print("✅ 問題は見つかりませんでした。")
        return

    print(f"⚠️  合計 {total} 件の問題が見つかりました。\n")

    if report["duplicates"]:
        print(f"[重複] {len(report['duplicates'])} 件")
        for dup in report["duplicates"]:
            print(f"  • {dup['command']}  ({len(dup['occurrences'])} 回)")

    if report["schedule_conflicts"]:
        print(f"\n[スケジュール集中] {len(report['schedule_conflicts'])} 件")
        for c in report["schedule_conflicts"]:
            print(f"  • {c['schedule_key']}  ({len(c['jobs'])} ジョブ)")

    if report["commented_jobs"]:
        print(f"\n[コメントアウト済み] {len(report['commented_jobs'])} 件")
        for c in report["commented_jobs"]:
            print(f"  • {c['line']}")

    if report["missing_scripts"]:
        print(f"\n[スクリプト不在] {len(report['missing_scripts'])} 件")
        for m in report["missing_scripts"]:
            print(f"  • {m['script']}")

    if report["openclaw_issues"]:
        print(f"\n[OpenClaw無効ジョブ] {len(report['openclaw_issues'])} 件")
        for issue in report["openclaw_issues"]:
            print(f"  • {issue['job'].get('task', 'unknown')}")

    print("\n[最適化提案]")
    for i, suggestion in enumerate(report["suggestions"], 1):
        print(f"  {i}. {suggestion}")

    if dry_run:
        print("\n[dry-run モード] 変更は行いません。提案のみです。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cronジョブの棚卸し・最適化ツール（提案のみ、自動変更なし）"
    )
    parser.add_argument(
        "--check-scripts",
        action="store_true",
        help="参照スクリプトの存在をチェックする",
    )
    parser.add_argument(
        "--openclaw-config",
        metavar="PATH",
        default=None,
        help="OpenClawのcron設定JSONファイルパス（例: /etc/openclaw.json）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="提案のみ表示（デフォルト動作と同じ）",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=4,
        help="スケジュール集中を検出する閾値（デフォルト: 4）",
    )
    args = parser.parse_args()

    # 1. crontab 取得
    crontab_text = _get_crontab_text()
    jobs = parse_crontab(crontab_text)
    active_jobs = [j for j in jobs if not j.is_comment]
    print(f"crontab: {len(active_jobs)} 件のアクティブなジョブを取得しました。")

    # 2. 各検出
    duplicates = detect_duplicates(jobs)
    conflicts = detect_schedule_conflicts(jobs, threshold=args.threshold)
    commented = detect_commented_jobs(jobs)
    missing = detect_missing_scripts(jobs) if args.check_scripts else []

    # 3. OpenClaw設定
    openclaw_result = None
    openclaw_issues: list[dict[str, Any]] = []
    if args.openclaw_config:
        openclaw_result = parse_openclaw_cron(args.openclaw_config)
        openclaw_issues = detect_openclaw_issues(openclaw_result)

    # 4. レポート生成
    report = generate_optimization_report(
        duplicates, conflicts, commented, missing, openclaw_issues
    )

    # 5. 出力
    _print_report(report, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
