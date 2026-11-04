"""
TDD tests for cron-optimizer.
Run: python3 -m pytest scripts/test_optimizer.py -v
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(__file__))

from optimizer import (
    CronJob,
    generate_optimization_report,
    parse_crontab,
    detect_duplicates,
    detect_schedule_conflicts,
    detect_commented_jobs,
    detect_missing_scripts,
    parse_openclaw_cron,
)


SAMPLE_CRONTAB = """\
# This is a comment
0 * * * * /usr/bin/python3 /home/user/scripts/backup.py
0 * * * * /usr/bin/python3 /home/user/scripts/backup.py
30 2 * * * /home/user/scripts/cleanup.sh
# 0 5 * * * /home/user/scripts/disabled.sh
0 * * * * /usr/bin/python3 /home/user/scripts/monitor.py
0 * * * * /usr/bin/python3 /home/user/scripts/report.py
0 * * * * /usr/bin/python3 /home/user/scripts/alert.py
*/5 * * * * /home/user/scripts/heartbeat.sh
"""


class TestParseCrontab(unittest.TestCase):
    def test_parse_basic(self):
        jobs = parse_crontab(SAMPLE_CRONTAB)
        # Should include active jobs only (not comment lines, not blank lines)
        active = [j for j in jobs if not j.is_comment]
        self.assertEqual(len(active), 7)

    def test_parse_schedule(self):
        jobs = parse_crontab(SAMPLE_CRONTAB)
        active = [j for j in jobs if not j.is_comment]
        # First active job
        first = active[0]
        self.assertEqual(first.minute, "0")
        self.assertEqual(first.hour, "*")
        self.assertEqual(first.command, "/usr/bin/python3 /home/user/scripts/backup.py")

    def test_parse_comment_lines(self):
        jobs = parse_crontab(SAMPLE_CRONTAB)
        comments = [j for j in jobs if j.is_comment]
        # "# This is a comment" and "# 0 5 * * * ..." are both comment lines
        self.assertGreaterEqual(len(comments), 1)

    def test_parse_empty(self):
        jobs = parse_crontab("")
        self.assertEqual(jobs, [])

    def test_parse_no_crontab(self):
        """crontab -l outputs 'no crontab for user' — should return empty list"""
        jobs = parse_crontab("no crontab for user\n")
        self.assertEqual(jobs, [])

    def test_cron_job_repr(self):
        jobs = parse_crontab("0 2 * * * /usr/bin/backup.sh\n")
        self.assertEqual(len(jobs), 1)
        self.assertIn("/usr/bin/backup.sh", repr(jobs[0]))


class TestDetectDuplicates(unittest.TestCase):
    def test_no_duplicates(self):
        crontab = "0 1 * * * /usr/bin/job_a.sh\n30 2 * * * /usr/bin/job_b.sh\n"
        jobs = parse_crontab(crontab)
        dups = detect_duplicates(jobs)
        self.assertEqual(dups, [])

    def test_duplicate_command(self):
        crontab = (
            "0 * * * * /usr/bin/backup.py\n"
            "0 * * * * /usr/bin/backup.py\n"
        )
        jobs = parse_crontab(crontab)
        dups = detect_duplicates(jobs)
        self.assertEqual(len(dups), 1)
        self.assertIn("/usr/bin/backup.py", dups[0]["command"])

    def test_duplicate_different_schedule(self):
        """Same command, different schedule → still a duplicate"""
        crontab = (
            "0 1 * * * /usr/bin/backup.py\n"
            "0 2 * * * /usr/bin/backup.py\n"
        )
        jobs = parse_crontab(crontab)
        dups = detect_duplicates(jobs)
        self.assertEqual(len(dups), 1)

    def test_duplicate_returns_all_occurrences(self):
        crontab = (
            "0 1 * * * /usr/bin/backup.py\n"
            "0 2 * * * /usr/bin/backup.py\n"
            "0 3 * * * /usr/bin/backup.py\n"
        )
        jobs = parse_crontab(crontab)
        dups = detect_duplicates(jobs)
        self.assertEqual(len(dups), 1)
        self.assertEqual(len(dups[0]["occurrences"]), 3)


class TestDetectScheduleConflicts(unittest.TestCase):
    def test_no_conflict(self):
        crontab = (
            "0 1 * * * /usr/bin/job_a.sh\n"
            "0 2 * * * /usr/bin/job_b.sh\n"
            "0 3 * * * /usr/bin/job_c.sh\n"
        )
        jobs = parse_crontab(crontab)
        conflicts = detect_schedule_conflicts(jobs, threshold=3)
        self.assertEqual(conflicts, [])

    def test_conflict_at_same_time(self):
        """5 jobs all at minute=0, hour=* → conflict"""
        crontab = (
            "0 * * * * /usr/bin/job_a.sh\n"
            "0 * * * * /usr/bin/job_b.sh\n"
            "0 * * * * /usr/bin/job_c.sh\n"
            "0 * * * * /usr/bin/job_d.sh\n"
            "0 * * * * /usr/bin/job_e.sh\n"
        )
        jobs = parse_crontab(crontab)
        conflicts = detect_schedule_conflicts(jobs, threshold=3)
        self.assertGreater(len(conflicts), 0)

    def test_conflict_threshold(self):
        crontab = (
            "0 * * * * /usr/bin/job_a.sh\n"
            "0 * * * * /usr/bin/job_b.sh\n"
        )
        jobs = parse_crontab(crontab)
        # threshold=2 → 2 jobs at same time is a conflict
        conflicts = detect_schedule_conflicts(jobs, threshold=2)
        self.assertGreater(len(conflicts), 0)

        # threshold=5 → not a conflict
        conflicts_high = detect_schedule_conflicts(jobs, threshold=5)
        self.assertEqual(conflicts_high, [])


class TestDetectCommentedJobs(unittest.TestCase):
    def test_no_commented_jobs(self):
        crontab = "0 1 * * * /usr/bin/job_a.sh\n# plain comment\n"
        jobs = parse_crontab(crontab)
        commented = detect_commented_jobs(jobs)
        self.assertEqual(commented, [])

    def test_commented_cron_job(self):
        crontab = "# 0 5 * * * /home/user/scripts/disabled.sh\n"
        jobs = parse_crontab(crontab)
        commented = detect_commented_jobs(jobs)
        self.assertEqual(len(commented), 1)
        self.assertIn("disabled.sh", commented[0]["line"])

    def test_mixed(self):
        crontab = (
            "# 0 5 * * * /scripts/disabled.sh\n"
            "0 1 * * * /scripts/active.sh\n"
            "# plain text comment\n"
        )
        jobs = parse_crontab(crontab)
        commented = detect_commented_jobs(jobs)
        self.assertEqual(len(commented), 1)


class TestDetectMissingScripts(unittest.TestCase):
    def test_all_scripts_exist(self):
        crontab = "0 1 * * * /usr/bin/python3 /scripts/existing.py\n"
        jobs = parse_crontab(crontab)
        with patch("os.path.exists", return_value=True):
            missing = detect_missing_scripts(jobs)
        self.assertEqual(missing, [])

    def test_missing_script(self):
        crontab = "0 1 * * * /scripts/nonexistent.sh\n"
        jobs = parse_crontab(crontab)
        with patch("os.path.exists", return_value=False):
            missing = detect_missing_scripts(jobs)
        self.assertEqual(len(missing), 1)
        self.assertIn("nonexistent.sh", missing[0]["script"])

    def test_builtin_command_skipped(self):
        """Commands without absolute path (e.g. 'echo hello') should be skipped"""
        crontab = "0 1 * * * echo hello world\n"
        jobs = parse_crontab(crontab)
        with patch("os.path.exists", return_value=False):
            missing = detect_missing_scripts(jobs)
        self.assertEqual(missing, [])

    def test_python_with_script_arg(self):
        """python3 /path/to/script.py → check script.py, not python3"""
        crontab = "0 1 * * * /usr/bin/python3 /home/user/myscript.py\n"
        jobs = parse_crontab(crontab)
        with patch("os.path.exists", return_value=False) as mock_exists:
            missing = detect_missing_scripts(jobs)
        self.assertEqual(len(missing), 1)
        self.assertIn("myscript.py", missing[0]["script"])


class TestGenerateOptimizationReport(unittest.TestCase):
    def test_empty_report(self):
        report = generate_optimization_report([], [], [], [], [])
        self.assertIn("issues", report)
        self.assertEqual(report["total_issues"], 0)

    def test_report_with_issues(self):
        dups = [{"command": "/usr/bin/backup.py", "occurrences": [MagicMock(), MagicMock()]}]
        conflicts = [{"schedule_key": "0 *", "jobs": [MagicMock(), MagicMock(), MagicMock()]}]
        report = generate_optimization_report(dups, conflicts, [], [], [])
        self.assertGreater(report["total_issues"], 0)
        self.assertIn("suggestions", report)

    def test_report_structure(self):
        report = generate_optimization_report([], [], [], [], [])
        self.assertIn("duplicates", report)
        self.assertIn("schedule_conflicts", report)
        self.assertIn("commented_jobs", report)
        self.assertIn("missing_scripts", report)
        self.assertIn("openclaw_issues", report)
        self.assertIn("suggestions", report)
        self.assertIn("total_issues", report)

    def test_suggestions_for_duplicates(self):
        dups = [{"command": "/usr/bin/backup.py", "occurrences": [MagicMock(), MagicMock()]}]
        report = generate_optimization_report(dups, [], [], [], [])
        suggestion_texts = " ".join(report["suggestions"])
        self.assertIn("重複", suggestion_texts)

    def test_suggestions_for_conflicts(self):
        conflicts = [{"schedule_key": "0 *", "jobs": [MagicMock()] * 5}]
        report = generate_optimization_report([], conflicts, [], [], [])
        suggestion_texts = " ".join(report["suggestions"])
        self.assertIn("集中", suggestion_texts)


class TestParseOpenclawCron(unittest.TestCase):
    def test_parse_valid_config(self):
        config = {
            "cron": [
                {"schedule": "0 * * * *", "task": "check-inbox", "enabled": True},
                {"schedule": "30 8 * * *", "task": "daily-report", "enabled": False},
            ]
        }
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(config))):
            with patch("os.path.exists", return_value=True):
                result = parse_openclaw_cron("/fake/openclaw.json")
        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual(result["jobs"][0]["task"], "check-inbox")

    def test_parse_missing_file(self):
        with patch("os.path.exists", return_value=False):
            result = parse_openclaw_cron("/fake/openclaw.json")
        self.assertIsNone(result)

    def test_parse_no_cron_key(self):
        config = {"other_key": "value"}
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(config))):
            with patch("os.path.exists", return_value=True):
                result = parse_openclaw_cron("/fake/openclaw.json")
        self.assertEqual(result["jobs"], [])

    def test_detect_disabled_openclaw_jobs(self):
        config = {
            "cron": [
                {"schedule": "0 * * * *", "task": "active-job", "enabled": True},
                {"schedule": "30 8 * * *", "task": "disabled-job", "enabled": False},
            ]
        }
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(config))):
            with patch("os.path.exists", return_value=True):
                result = parse_openclaw_cron("/fake/openclaw.json")
        disabled = [j for j in result["jobs"] if not j.get("enabled", True)]
        self.assertEqual(len(disabled), 1)
        self.assertEqual(disabled[0]["task"], "disabled-job")


if __name__ == "__main__":
    unittest.main()
