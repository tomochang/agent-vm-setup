"""
schedule-optimizer — 日程調整の自動最適化スクリプト
Python 3.10+ 標準ライブラリのみ使用

Usage:
  python3 scripts/optimizer.py --date-range 2026-03-10:2026-03-14 --duration 60 \\
      [--events-file events.json | --events-stdin] \\
      [--buffer-for bank] [--avoid-morning] [--config config.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
import zoneinfo

# ────────────────────────────────────────────────────────────
# 定数
# ────────────────────────────────────────────────────────────

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


# ────────────────────────────────────────────────────────────
# 型エイリアス
# ────────────────────────────────────────────────────────────

Event = dict[str, Any]
Slot  = tuple[datetime, datetime]


# ────────────────────────────────────────────────────────────
# 設定
# ────────────────────────────────────────────────────────────

def default_config() -> dict:
    return {
        "business_hours": {"start": "09:00", "end": "18:00"},
        "timezone": "Asia/Tokyo",
        "avoid_morning": True,
        "default_slot_duration_minutes": 60,
        "buffer_rules": [
            {"keyword": "bank", "before_minutes": 60, "after_minutes": 60},
            {"keyword": "銀行", "before_minutes": 60, "after_minutes": 60},
        ],
        "exclude_weekends": True,
    }


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    # 不足キーはデフォルトで補完
    base = default_config()
    base.update(cfg)
    return base


# ────────────────────────────────────────────────────────────
# カレンダーイベントのパース
# ────────────────────────────────────────────────────────────

def _parse_datetime(raw: str, tz: zoneinfo.ZoneInfo) -> datetime:
    """ISO 8601 文字列 → timezone-aware datetime (tz に変換)"""
    # Python 3.11+ は fromisoformat で +09:00 を正しく扱う
    # 3.10 でも "+09:00" サフィックスは動作する
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def parse_calendar_events(raw_json: str, timezone: str = "Asia/Tokyo") -> list[Event]:
    """
    gogcli の calendar events --json 出力（またはそれに準拠したJSON）をパースする。

    入力例:
      [{"id":"...", "summary":"...", "start": {"dateTime":"2026-03-10T09:00:00+09:00"}, "end": {...}}]

    全日イベントは {"date": "2026-03-10"} 形式。
    """
    tz  = zoneinfo.ZoneInfo(timezone)
    raw = json.loads(raw_json)

    # gogcli は {"events": [...]} 形式で返す場合がある
    if isinstance(raw, dict) and "events" in raw:
        raw = raw["events"]

    events: list[Event] = []
    for item in raw:
        summary  = item.get("summary", "")
        start_raw = item.get("start", {})
        end_raw   = item.get("end",   {})

        if "date" in start_raw:
            # 全日イベント
            events.append({
                "id":      item.get("id"),
                "summary": summary,
                "start":   date.fromisoformat(start_raw["date"]),
                "end":     date.fromisoformat(end_raw["date"]),
                "all_day": True,
            })
        else:
            dt_start = _parse_datetime(start_raw["dateTime"], tz)
            dt_end   = _parse_datetime(end_raw["dateTime"],   tz)
            events.append({
                "id":      item.get("id"),
                "summary": summary,
                "start":   dt_start,
                "end":     dt_end,
                "all_day": False,
            })

    return events


# ────────────────────────────────────────────────────────────
# バッファルールの適用
# ────────────────────────────────────────────────────────────

def apply_buffer_rules(events: list[Event], config: dict) -> list[Event]:
    """
    buffer_rules に合致する予定の前後にバッファ時間を追加して
    新しいイベントリストを返す（元リストは変更しない）。
    """
    rules       = config.get("buffer_rules", [])
    tz          = zoneinfo.ZoneInfo(config.get("timezone", "Asia/Tokyo"))
    result: list[Event] = []

    for ev in events:
        if ev.get("all_day"):
            result.append(ev)
            continue

        matched_before = 0
        matched_after  = 0
        summary_lower  = ev["summary"].lower()

        for rule in rules:
            keyword = rule["keyword"].lower()
            if keyword in summary_lower:
                matched_before = max(matched_before, rule.get("before_minutes", 0))
                matched_after  = max(matched_after,  rule.get("after_minutes",  0))

        new_start = ev["start"] - timedelta(minutes=matched_before)
        new_end   = ev["end"]   + timedelta(minutes=matched_after)

        result.append({**ev, "start": new_start, "end": new_end})

    return result


# ────────────────────────────────────────────────────────────
# 空きスロットの算出
# ────────────────────────────────────────────────────────────

def find_free_slots(events: list[Event], target_date: date, config: dict) -> list[Slot]:
    """
    target_date の営業時間内で、events によって塞がれていない空きスロットを返す。
    """
    tz = zoneinfo.ZoneInfo(config.get("timezone", "Asia/Tokyo"))
    bh = config.get("business_hours", {"start": "09:00", "end": "18:00"})

    bh_start_h, bh_start_m = map(int, bh["start"].split(":"))
    bh_end_h,   bh_end_m   = map(int, bh["end"].split(":"))

    day_start = datetime(target_date.year, target_date.month, target_date.day,
                         bh_start_h, bh_start_m, tzinfo=tz)
    day_end   = datetime(target_date.year, target_date.month, target_date.day,
                         bh_end_h,   bh_end_m,   tzinfo=tz)

    # 当日の予定だけ抽出（全日イベントは終日ブロック扱い）
    day_events: list[tuple[datetime, datetime]] = []
    for ev in events:
        if ev.get("all_day"):
            start_date = ev["start"] if isinstance(ev["start"], date) else ev["start"].date()
            end_date   = ev["end"]   if isinstance(ev["end"],   date) else ev["end"].date()
            if start_date <= target_date < end_date:
                # 終日ブロック
                day_events.append((day_start, day_end))
        else:
            ev_start: datetime = ev["start"]
            ev_end:   datetime = ev["end"]
            if ev_start.date() == target_date or ev_end.date() == target_date:
                # 当日にかかるイベント
                s = max(ev_start, day_start)
                e = min(ev_end,   day_end)
                if s < e:
                    day_events.append((s, e))

    # タイムラインをマージしてギャップ（空き）を算出
    day_events.sort(key=lambda x: x[0])

    free: list[Slot] = []
    cursor = day_start

    for ev_start, ev_end in day_events:
        if ev_start > cursor:
            free.append((cursor, ev_start))
        cursor = max(cursor, ev_end)

    if cursor < day_end:
        free.append((cursor, day_end))

    return free


# ────────────────────────────────────────────────────────────
# 午前NG フィルタ
# ────────────────────────────────────────────────────────────

_MORNING_END_HOUR = 13  # 13:00 以降を「午後」とする


def filter_avoid_morning(slots: list[Slot], avoid_morning: bool) -> list[Slot]:
    """
    avoid_morning=True のとき、13:00 より前のスロット（または部分）を除去する。
    スロットが午前から午後にまたがる場合は 13:00 に切り詰める。
    """
    if not avoid_morning:
        return slots

    result: list[Slot] = []
    for s, e in slots:
        # 午後境界
        afternoon = s.replace(hour=_MORNING_END_HOUR, minute=0, second=0, microsecond=0)
        if e <= afternoon:
            # スロット全体が午前 → 捨てる
            continue
        # スロットの一部が午後にかかる → 開始を afternoon に切り詰め
        new_start = max(s, afternoon)
        if new_start < e:
            result.append((new_start, e))

    return result


# ────────────────────────────────────────────────────────────
# 土日除外
# ────────────────────────────────────────────────────────────

def exclude_weekends(dates: list[date]) -> list[date]:
    """土曜(5)・日曜(6) を除外して返す。"""
    return [d for d in dates if d.weekday() < 5]


# ────────────────────────────────────────────────────────────
# 衝突検出
# ────────────────────────────────────────────────────────────

def has_conflict(
    candidate_start: datetime,
    candidate_end:   datetime,
    events: list[Event],
) -> bool:
    """
    candidate が events のいずれかと重なるか判定する。
    端点が接しているだけ（e.g. 10:00-10:00）は衝突なし。
    """
    for ev in events:
        if ev.get("all_day"):
            continue
        ev_start: datetime = ev["start"]
        ev_end:   datetime = ev["end"]
        # 重なり判定: candidate_start < ev_end AND candidate_end > ev_start
        if candidate_start < ev_end and candidate_end > ev_start:
            return True
    return False


# ────────────────────────────────────────────────────────────
# 候補フォーマット
# ────────────────────────────────────────────────────────────

def format_candidate(start: datetime, end: datetime) -> str:
    """「3/10（月）14:00-15:00」形式の文字列を生成する。"""
    weekday = WEEKDAY_JP[start.weekday()]
    return (
        f"{start.month}/{start.day}（{weekday}）"
        f"{start.hour:02d}:{start.minute:02d}"
        f"-"
        f"{end.hour:02d}:{end.minute:02d}"
    )


def format_candidates_email(candidates: list[Slot]) -> str:
    """複数候補をビジネスメール用の箇条書きテキストに変換する。"""
    if not candidates:
        return "候補日程が見つかりませんでした。"
    lines = ["ご都合のよろしい日程をご確認ください。\n"]
    for i, (s, e) in enumerate(candidates, 1):
        lines.append(f"  {i}. {format_candidate(s, e)}")
    lines.append("\nどうぞよろしくお願いいたします。")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
# メイン：候補生成
# ────────────────────────────────────────────────────────────

def generate_candidates(
    events: list[Event],
    start_date: date,
    end_date: date,
    duration_minutes: int,
    config: dict,
    avoid_morning: bool | None = None,
) -> list[Slot]:
    """
    start_date〜end_date の範囲で duration_minutes の空きスロット候補を生成する。
    バッファルール・土日除外・午前NG を自動適用する。
    """
    if avoid_morning is None:
        avoid_morning = config.get("avoid_morning", True)

    # バッファ適用済みイベント
    buffered_events = apply_buffer_rules(events, config)

    # 対象日リスト
    total_days = (end_date - start_date).days + 1
    all_dates  = [start_date + timedelta(days=i) for i in range(total_days)]

    if config.get("exclude_weekends", True):
        all_dates = exclude_weekends(all_dates)

    candidates: list[Slot] = []
    duration = timedelta(minutes=duration_minutes)

    for d in all_dates:
        free = find_free_slots(buffered_events, d, config)
        free = filter_avoid_morning(free, avoid_morning)

        for slot_start, slot_end in free:
            cursor = slot_start
            while cursor + duration <= slot_end:
                cand_end = cursor + duration
                if not has_conflict(cursor, cand_end, buffered_events):
                    candidates.append((cursor, cand_end))
                cursor += duration  # 1枠ずつ進める（重複なしの非重複スロット）

    return candidates


# ────────────────────────────────────────────────────────────
# CLI エントリポイント
# ────────────────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="schedule-optimizer: 日程候補を自動生成する")
    p.add_argument("--date-range", required=True,
                   help="対象期間 (例: 2026-03-10:2026-03-14)")
    p.add_argument("--duration", type=int, default=60,
                   help="1コマの長さ（分）。デフォルト: 60")
    p.add_argument("--events-file",
                   help="カレンダーイベントJSON ファイルパス (省略時は stdin)")
    p.add_argument("--avoid-morning", action="store_true",
                   help="午前NG: 13:00以降のみ候補に含める")
    p.add_argument("--buffer-for",
                   help="バッファを追加するキーワード (例: bank)")
    p.add_argument("--config",
                   default=str(Path(__file__).parent / "config.json"),
                   help="設定ファイルパス")
    p.add_argument("--format", choices=["text", "json", "email"],
                   default="text", help="出力形式")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # 設定ロード
    config_path = Path(args.config)
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = default_config()

    # CLI フラグで上書き
    if args.avoid_morning:
        config["avoid_morning"] = True

    # 期間パース
    parts = args.date_range.split(":")
    start_date = date.fromisoformat(parts[0])
    end_date   = date.fromisoformat(parts[1])

    # イベント読み込み
    if args.events_file:
        raw_json = Path(args.events_file).read_text(encoding="utf-8")
    else:
        raw_json = sys.stdin.read()

    if raw_json.strip():
        events = parse_calendar_events(raw_json, config.get("timezone", "Asia/Tokyo"))
    else:
        events = []

    # 候補生成
    candidates = generate_candidates(
        events=events,
        start_date=start_date,
        end_date=end_date,
        duration_minutes=args.duration,
        config=config,
    )

    # 出力
    if args.format == "json":
        out = [{"start": s.isoformat(), "end": e.isoformat()} for s, e in candidates]
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.format == "email":
        print(format_candidates_email(candidates))
    else:
        for s, e in candidates:
            print(format_candidate(s, e))


if __name__ == "__main__":
    main()
