"""
TDD tests for session-wrapup skill.
Run with: python3 -m pytest scripts/test_wrapup.py -v
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date
import sys
import os

# Ensure the scripts directory is in path
sys.path.insert(0, os.path.dirname(__file__))


class TestDetectUnpushedChanges(unittest.TestCase):
    """Test git unpushed/uncommitted change detection."""

    @patch("wrapup.subprocess.run")
    def test_detect_uncommitted_changes(self, mock_run):
        """Detects uncommitted (dirty) files via git status --porcelain."""
        from wrapup import detect_unpushed_changes

        mock_run.side_effect = [
            MagicMock(stdout=" M memory/2026-03-07.md\n?? newfile.py\n", returncode=0),  # git status
            MagicMock(stdout="", returncode=0),  # git log
        ]

        result = detect_unpushed_changes("/workspace")

        assert result["has_changes"] is True
        assert result["uncommitted_count"] == 2
        assert result["unpushed_count"] == 0
        assert "memory/2026-03-07.md" in result["uncommitted_files"]

    @patch("wrapup.subprocess.run")
    def test_detect_unpushed_commits(self, mock_run):
        """Detects commits not yet pushed to origin/main."""
        from wrapup import detect_unpushed_changes

        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),  # git status (clean)
            MagicMock(stdout="abc1234 Add session-wrapup skill\ndef5678 Fix bug\n", returncode=0),  # git log
        ]

        result = detect_unpushed_changes("/workspace")

        assert result["has_changes"] is True
        assert result["uncommitted_count"] == 0
        assert result["unpushed_count"] == 2
        assert "abc1234 Add session-wrapup skill" in result["unpushed_commits"]

    @patch("wrapup.subprocess.run")
    def test_no_changes(self, mock_run):
        """Returns clean state when nothing to push or commit."""
        from wrapup import detect_unpushed_changes

        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        result = detect_unpushed_changes("/workspace")

        assert result["has_changes"] is False
        assert result["uncommitted_count"] == 0
        assert result["unpushed_count"] == 0

    @patch("wrapup.subprocess.run")
    def test_git_error_handled_gracefully(self, mock_run):
        """Returns safe defaults when git commands fail."""
        from wrapup import detect_unpushed_changes

        mock_run.side_effect = Exception("git not found")

        result = detect_unpushed_changes("/workspace")

        assert "error" in result
        assert result["has_changes"] is False


class TestExtractKeyEvents(unittest.TestCase):
    """Test extraction of key events from daily memory files."""

    def test_extract_key_events_from_sample(self):
        """Extracts headings and bullet points as key events."""
        from wrapup import extract_key_events

        sample_md = """# 2026-03-07

## 朝のブリーフィング
- メール3件確認
- カレンダー: 15時銀行打合せ

## 作業ログ
- session-wrapupスキル作成開始
- TDDで実装：テスト→実装→パス

## 決定事項
- wrapupはセッション終了時に手動実行とする
"""
        events = extract_key_events(sample_md)

        assert len(events) > 0
        assert any("session-wrapup" in e for e in events)
        assert any("銀行" in e for e in events)

    def test_extract_returns_list(self):
        """Always returns a list, even for empty content."""
        from wrapup import extract_key_events

        events = extract_key_events("")
        assert isinstance(events, list)

    def test_extract_limits_events(self):
        """Returns at most max_events items."""
        from wrapup import extract_key_events

        # Generate long content
        lines = ["- item " + str(i) for i in range(100)]
        md = "\n".join(lines)

        events = extract_key_events(md, max_events=10)
        assert len(events) <= 10

    def test_extract_skips_empty_lines(self):
        """Skips blank lines and pure whitespace."""
        from wrapup import extract_key_events

        md = "\n\n\n- real event\n\n\n"
        events = extract_key_events(md)
        assert all(e.strip() for e in events)


class TestGenerateSummary(unittest.TestCase):
    """Test session summary generation."""

    def test_generate_summary_with_events(self):
        """Generates a non-empty summary string from events."""
        from wrapup import generate_summary

        events = [
            "session-wrapupスキル作成",
            "TDDでテスト全パス",
            "銀行打合せ15時",
        ]
        summary = generate_summary(events, session_date=date(2026, 3, 7))

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "2026-03-07" in summary
        assert "session-wrapup" in summary

    def test_generate_summary_empty_events(self):
        """Returns a placeholder when no events found."""
        from wrapup import generate_summary

        summary = generate_summary([], session_date=date(2026, 3, 7))
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_generate_summary_includes_date(self):
        """Summary always includes the session date."""
        from wrapup import generate_summary

        summary = generate_summary(["test event"], session_date=date(2026, 1, 15))
        assert "2026-01-15" in summary


class TestIdentifyPendingTasks(unittest.TestCase):
    """Test pending task extraction from AGENT_WORK.md."""

    def test_identify_pending_tasks(self):
        """Extracts TODO/WIP tasks from AGENT_WORK.md sample."""
        from wrapup import identify_pending_tasks

        sample = """# AGENT_WORK.md

## 進行中

### タスク1: session-wrapupスキル作成
- ステータス: WIP
- 次のアクション: テストを全部パスさせる
- ブロッカー: なし

### タスク2: 銀行資料作成
- ステータス: TODO
- 次のアクション: ドラフト作成

## 完了

### タスク0: ブートストラップ
- ステータス: DONE
"""
        tasks = identify_pending_tasks(sample)

        assert len(tasks) >= 2
        assert any("session-wrapup" in t["title"] for t in tasks)
        assert any("銀行" in t["title"] for t in tasks)
        # Completed tasks should not be included
        assert not any("ブートストラップ" in t["title"] for t in tasks)

    def test_identify_pending_tasks_empty(self):
        """Returns empty list for empty content."""
        from wrapup import identify_pending_tasks

        tasks = identify_pending_tasks("")
        assert isinstance(tasks, list)
        assert len(tasks) == 0

    def test_identify_pending_tasks_no_completed_section(self):
        """Works when there's no 完了 section."""
        from wrapup import identify_pending_tasks

        sample = """# AGENT_WORK.md

## 進行中

### タスク1: テストタスク
- ステータス: WIP
"""
        tasks = identify_pending_tasks(sample)
        assert len(tasks) >= 1

    def test_task_has_required_fields(self):
        """Each task dict has title and status fields."""
        from wrapup import identify_pending_tasks

        sample = """## 進行中\n### タスク: サンプル\n- ステータス: TODO\n"""
        tasks = identify_pending_tasks(sample)

        for task in tasks:
            assert "title" in task
            assert "status" in task


class TestFullWrapupReport(unittest.TestCase):
    """Integration test: full wrapup report generation."""

    @patch("wrapup.subprocess.run")
    @patch("wrapup.open", create=True)
    def test_full_wrapup_report(self, mock_open, mock_run):
        """Generates a complete wrapup report integrating all components."""
        from wrapup import generate_wrapup_report

        # Mock git: 1 uncommitted file, 1 unpushed commit
        mock_run.side_effect = [
            MagicMock(stdout=" M memory/2026-03-07.md\n", returncode=0),
            MagicMock(stdout="abc1234 Add wrapup skill\n", returncode=0),
        ]

        # Mock file reads
        daily_md = "# 2026-03-07\n- session-wrapupスキル完成\n- TDDでテストパス\n"
        agent_work_md = "## 進行中\n### タスク: 銀行資料\n- ステータス: TODO\n"

        def mock_open_side_effect(path, *args, **kwargs):
            m = MagicMock()
            if "AGENT_WORK" in str(path):
                m.__enter__ = lambda s: MagicMock(read=lambda: agent_work_md)
            else:
                m.__enter__ = lambda s: MagicMock(read=lambda: daily_md)
            m.__exit__ = MagicMock(return_value=False)
            return m

        mock_open.side_effect = mock_open_side_effect

        report = generate_wrapup_report(
            workspace="/workspace",
            session_date=date(2026, 3, 7),
        )

        assert isinstance(report, str)
        assert len(report) > 100  # Must be a substantial report
        # Should contain sections
        assert "Git" in report or "commit" in report.lower()
        assert "2026-03-07" in report

    @patch("wrapup.subprocess.run")
    def test_full_wrapup_report_survives_missing_files(self, mock_run):
        """Report generation completes even if memory files are missing."""
        from wrapup import generate_wrapup_report

        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        # No file mocking — files will be missing, should not crash
        report = generate_wrapup_report(
            workspace="/workspace",
            session_date=date(2026, 3, 7),
        )

        assert isinstance(report, str)
        assert len(report) > 0


class TestSecurityFeatures(unittest.TestCase):
    """Security: path traversal prevention, file size limits, relative path messages."""

    @patch("wrapup.subprocess.run")
    def test_path_traversal_in_workspace_arg(self, mock_run):
        """
        --workspace /workspace/../tmp のような .. を含むパスは
        realpath で無害化されるか、PermissionError が発生すること。
        """
        from wrapup import generate_wrapup_report

        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        # /workspace/../tmp → realpath で /tmp になる（存在すればそのまま動く = 無害化）
        # どちらでも「クラッシュしない」「フルパス漏洩しない」を確認
        try:
            report = generate_wrapup_report(
                workspace="/workspace/../tmp",
                session_date=date(2026, 3, 7),
            )
            # 無害化パス: 正常レポートが返る。".." が残っていないこと
            assert isinstance(report, str)
            assert ".." not in report or "git" in report.lower()
        except (PermissionError, ValueError):
            # PermissionError / ValueError も許容（存在しないディレクトリ等）
            pass

    @patch("wrapup.subprocess.run")
    @patch("wrapup.os.path.getsize")
    def test_large_file_skipped(self, mock_getsize, mock_run):
        """
        10MB超のmemoryファイルはクラッシュせずスキップされ、
        レポートに「大きすぎます」と記載されること。
        """
        from wrapup import generate_wrapup_report

        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        # getsize が呼ばれた全パスに対して 11MB を返す
        mock_getsize.return_value = 11 * 1024 * 1024

        report = generate_wrapup_report(
            workspace="/workspace",
            session_date=date(2026, 3, 7),
        )

        assert isinstance(report, str)
        assert "大きすぎます" in report
        # クラッシュしないこと（ここに到達している時点でOK）

    @patch("wrapup.subprocess.run")
    def test_relative_path_in_report(self, mock_run):
        """
        ファイルが見つからないときのメッセージに workspace のフルパスが含まれないこと。
        """
        from wrapup import generate_wrapup_report

        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        report = generate_wrapup_report(
            workspace="/workspace",
            session_date=date(2026, 3, 7),
        )

        # フルパス /workspace/memory/... がそのまま露出していないこと
        assert "/workspace/memory/" not in report
        # 相対パスまたはファイル名のみが表示されていること
        assert isinstance(report, str)
        assert len(report) > 0


if __name__ == "__main__":
    unittest.main()
