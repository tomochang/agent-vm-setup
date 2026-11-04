"""
TDD tests for schedule-optimizer
Run: python3 -m pytest scripts/test_optimizer.py -v
"""

import json
import sys
import os
from datetime import datetime, date, time, timedelta
import zoneinfo

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(__file__))

import optimizer as opt

TZ = zoneinfo.ZoneInfo("Asia/Tokyo")


def dt(date_str: str, time_str: str) -> datetime:
    """Helper: create a timezone-aware datetime in JST."""
    d = date.fromisoformat(date_str)
    t = time.fromisoformat(time_str)
    return datetime.combine(d, t, tzinfo=TZ)


# ─────────────────────────────────────────────
# 1. test_parse_calendar_events
# ─────────────────────────────────────────────

def test_parse_calendar_events():
    """Parse gogcli-style calendar JSON output into internal event list."""
    raw = json.dumps([
        {
            "id": "abc123",
            "summary": "朝会",
            "start": {"dateTime": "2026-03-10T09:00:00+09:00"},
            "end":   {"dateTime": "2026-03-10T10:00:00+09:00"},
        },
        {
            "id": "def456",
            "summary": "ランチ",
            "start": {"dateTime": "2026-03-10T12:00:00+09:00"},
            "end":   {"dateTime": "2026-03-10T13:00:00+09:00"},
        },
    ])

    events = opt.parse_calendar_events(raw)
    assert len(events) == 2
    assert events[0]["summary"] == "朝会"
    assert events[0]["start"] == dt("2026-03-10", "09:00:00")
    assert events[0]["end"]   == dt("2026-03-10", "10:00:00")
    assert events[1]["summary"] == "ランチ"


def test_parse_calendar_events_all_day():
    """All-day events (date only) are parsed but treated as full-day blocks."""
    raw = json.dumps([
        {
            "id": "allday1",
            "summary": "祝日",
            "start": {"date": "2026-03-11"},
            "end":   {"date": "2026-03-12"},
        }
    ])
    events = opt.parse_calendar_events(raw)
    assert len(events) == 1
    assert events[0]["all_day"] is True


# ─────────────────────────────────────────────
# 2. test_find_free_slots
# ─────────────────────────────────────────────

def test_find_free_slots_basic():
    """9-10会議、12-13ランチ → 10-12 と 13-18 が空き"""
    events = [
        {"summary": "朝会",   "start": dt("2026-03-10", "09:00:00"), "end": dt("2026-03-10", "10:00:00"), "all_day": False},
        {"summary": "ランチ", "start": dt("2026-03-10", "12:00:00"), "end": dt("2026-03-10", "13:00:00"), "all_day": False},
    ]
    config = opt.default_config()
    free = opt.find_free_slots(events, date(2026, 3, 10), config)

    assert len(free) == 2
    assert free[0] == (dt("2026-03-10", "10:00:00"), dt("2026-03-10", "12:00:00"))
    assert free[1] == (dt("2026-03-10", "13:00:00"), dt("2026-03-10", "18:00:00"))


def test_find_free_slots_no_events():
    """予定なし → 9-18 が全部空き"""
    config = opt.default_config()
    free = opt.find_free_slots([], date(2026, 3, 10), config)
    assert len(free) == 1
    assert free[0] == (dt("2026-03-10", "09:00:00"), dt("2026-03-10", "18:00:00"))


def test_find_free_slots_adjacent_events():
    """連続した予定は隙間なし"""
    events = [
        {"summary": "A", "start": dt("2026-03-10", "09:00:00"), "end": dt("2026-03-10", "12:00:00"), "all_day": False},
        {"summary": "B", "start": dt("2026-03-10", "12:00:00"), "end": dt("2026-03-10", "18:00:00"), "all_day": False},
    ]
    config = opt.default_config()
    free = opt.find_free_slots(events, date(2026, 3, 10), config)
    assert free == []


# ─────────────────────────────────────────────
# 3. test_apply_buffer
# ─────────────────────────────────────────────

def test_apply_buffer_bank():
    """銀行系予定に前後1hバッファ追加後の空き算出"""
    events = [
        {
            "summary": "銀行 打ち合わせ",
            "start": dt("2026-03-10", "14:00:00"),
            "end":   dt("2026-03-10", "15:00:00"),
            "all_day": False,
        }
    ]
    config = opt.default_config()
    buffered = opt.apply_buffer_rules(events, config)

    # バッファ後: 13:00-16:00 がブロックされるはず
    assert buffered[0]["start"] == dt("2026-03-10", "13:00:00")
    assert buffered[0]["end"]   == dt("2026-03-10", "16:00:00")


def test_apply_buffer_non_bank():
    """銀行以外の予定はバッファなし"""
    events = [
        {
            "summary": "社内MTG",
            "start": dt("2026-03-10", "14:00:00"),
            "end":   dt("2026-03-10", "15:00:00"),
            "all_day": False,
        }
    ]
    config = opt.default_config()
    buffered = opt.apply_buffer_rules(events, config)
    assert buffered[0]["start"] == dt("2026-03-10", "14:00:00")
    assert buffered[0]["end"]   == dt("2026-03-10", "15:00:00")


def test_apply_buffer_english_bank():
    """英語キーワード bank にも対応"""
    events = [
        {
            "summary": "Mizuho Bank Meeting",
            "start": dt("2026-03-10", "10:00:00"),
            "end":   dt("2026-03-10", "11:00:00"),
            "all_day": False,
        }
    ]
    config = opt.default_config()
    buffered = opt.apply_buffer_rules(events, config)
    assert buffered[0]["start"] == dt("2026-03-10", "09:00:00")
    assert buffered[0]["end"]   == dt("2026-03-10", "12:00:00")


# ─────────────────────────────────────────────
# 4. test_avoid_morning
# ─────────────────────────────────────────────

def test_avoid_morning():
    """avoid_morning=True で午後（13:00以降）のスロットのみ返す"""
    free_slots = [
        (dt("2026-03-10", "10:00:00"), dt("2026-03-10", "12:00:00")),
        (dt("2026-03-10", "13:00:00"), dt("2026-03-10", "18:00:00")),
    ]
    result = opt.filter_avoid_morning(free_slots, avoid_morning=True)
    assert len(result) == 1
    assert result[0][0].hour == 13


def test_avoid_morning_disabled():
    """avoid_morning=False ではフィルタなし"""
    free_slots = [
        (dt("2026-03-10", "10:00:00"), dt("2026-03-10", "12:00:00")),
        (dt("2026-03-10", "13:00:00"), dt("2026-03-10", "18:00:00")),
    ]
    result = opt.filter_avoid_morning(free_slots, avoid_morning=False)
    assert len(result) == 2


def test_avoid_morning_partial_slot():
    """スロットが午前から午後にまたがる場合は13:00からに切り詰め"""
    free_slots = [
        (dt("2026-03-10", "10:00:00"), dt("2026-03-10", "16:00:00")),
    ]
    result = opt.filter_avoid_morning(free_slots, avoid_morning=True)
    assert len(result) == 1
    assert result[0][0] == dt("2026-03-10", "13:00:00")
    assert result[0][1] == dt("2026-03-10", "16:00:00")


# ─────────────────────────────────────────────
# 5. test_exclude_weekends
# ─────────────────────────────────────────────

def test_exclude_weekends():
    """土日（2026-03-14土, 2026-03-15日）を除外"""
    dates = [
        date(2026, 3, 13),  # 金
        date(2026, 3, 14),  # 土
        date(2026, 3, 15),  # 日
        date(2026, 3, 16),  # 月
    ]
    result = opt.exclude_weekends(dates)
    assert date(2026, 3, 14) not in result
    assert date(2026, 3, 15) not in result
    assert date(2026, 3, 13) in result
    assert date(2026, 3, 16) in result


# ─────────────────────────────────────────────
# 6. test_conflict_detection
# ─────────────────────────────────────────────

def test_conflict_detection_no_conflict():
    """新規候補が既存予定と重ならない"""
    existing = [
        {"summary": "朝会", "start": dt("2026-03-10", "09:00:00"), "end": dt("2026-03-10", "10:00:00"), "all_day": False},
    ]
    candidate_start = dt("2026-03-10", "10:00:00")
    candidate_end   = dt("2026-03-10", "11:00:00")
    assert opt.has_conflict(candidate_start, candidate_end, existing) is False


def test_conflict_detection_overlap():
    """新規候補が既存予定と重なる"""
    existing = [
        {"summary": "朝会", "start": dt("2026-03-10", "09:00:00"), "end": dt("2026-03-10", "10:30:00"), "all_day": False},
    ]
    candidate_start = dt("2026-03-10", "10:00:00")
    candidate_end   = dt("2026-03-10", "11:00:00")
    assert opt.has_conflict(candidate_start, candidate_end, existing) is True


def test_conflict_detection_touching():
    """スタートとエンドが接している（=衝突なし）"""
    existing = [
        {"summary": "朝会", "start": dt("2026-03-10", "09:00:00"), "end": dt("2026-03-10", "10:00:00"), "all_day": False},
    ]
    candidate_start = dt("2026-03-10", "10:00:00")
    candidate_end   = dt("2026-03-10", "11:00:00")
    assert opt.has_conflict(candidate_start, candidate_end, existing) is False


# ─────────────────────────────────────────────
# 7. test_generate_candidate_text
# ─────────────────────────────────────────────

def test_generate_candidate_text():
    """「3/9（月）14:00-15:00」形式の候補文生成（2026-03-09は月曜日）"""
    start = dt("2026-03-09", "14:00:00")
    end   = dt("2026-03-09", "15:00:00")
    text = opt.format_candidate(start, end)
    assert text == "3/9（月）14:00-15:00"


def test_generate_candidate_text_tuesday():
    """火曜日（2026-03-10は火曜日）"""
    start = dt("2026-03-10", "10:00:00")
    end   = dt("2026-03-10", "11:30:00")
    text = opt.format_candidate(start, end)
    assert text == "3/10（火）10:00-11:30"


def test_generate_candidate_text_list():
    """複数候補をビジネスメール形式にフォーマット"""
    candidates = [
        (dt("2026-03-09", "14:00:00"), dt("2026-03-09", "15:00:00")),
        (dt("2026-03-10", "10:00:00"), dt("2026-03-10", "11:00:00")),
    ]
    text = opt.format_candidates_email(candidates)
    assert "3/9（月）14:00-15:00" in text
    assert "3/10（火）10:00-11:00" in text


# ─────────────────────────────────────────────
# 8. test_multiple_day_range
# ─────────────────────────────────────────────

def test_multiple_day_range():
    """複数日にわたる候補をまとめて生成（2026-03-10〜2026-03-14、60分枠）"""
    # 各日に1件ずつ予定があり、残りが空きになるケース
    events = [
        {"summary": "朝会",   "start": dt("2026-03-10", "09:00:00"), "end": dt("2026-03-10", "10:00:00"), "all_day": False},
        {"summary": "全社MTG","start": dt("2026-03-11", "09:00:00"), "end": dt("2026-03-11", "18:00:00"), "all_day": False},  # 空きなし
        {"summary": "ランチ", "start": dt("2026-03-12", "12:00:00"), "end": dt("2026-03-12", "13:00:00"), "all_day": False},
    ]
    config = opt.default_config()
    config["avoid_morning"] = False  # 午前NGは切る

    result = opt.generate_candidates(
        events=events,
        start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 14),
        duration_minutes=60,
        config=config,
    )

    # 2026-03-11 は全日塞がっているので候補ゼロ
    dates_with_candidates = {c[0].date() for c in result}
    assert date(2026, 3, 11) not in dates_with_candidates

    # 2026-03-10 に 10:00-11:00 が含まれるはず
    assert any(
        c[0] == dt("2026-03-10", "10:00:00") and c[1] == dt("2026-03-10", "11:00:00")
        for c in result
    )

    # 土日（3/14 土）は除外
    assert date(2026, 3, 14) not in dates_with_candidates


def test_multiple_day_range_with_buffer():
    """銀行予定バッファ込みで複数日生成"""
    events = [
        {
            "summary": "銀行訪問",
            "start": dt("2026-03-10", "14:00:00"),
            "end":   dt("2026-03-10", "15:00:00"),
            "all_day": False,
        }
    ]
    config = opt.default_config()
    config["avoid_morning"] = False

    result = opt.generate_candidates(
        events=events,
        start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 10),
        duration_minutes=60,
        config=config,
    )

    # バッファで 13:00-16:00 がブロック → 9-13 と 16-18 が空き
    starts = [c[0].hour for c in result]
    # 16:00-17:00 が入っているはず
    assert 16 in starts
    # 13:00-14:00 は入らない（バッファでブロック）
    assert 13 not in starts
