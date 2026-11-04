---
name: schedule-optimizer
description: 日程調整の自動最適化（空き時間マージ・候補生成・バッファ計算）
---

# schedule-optimizer

Googleカレンダーの予定データから空きスロットを算出し、ビジネスメール用の候補文を自動生成するスキル。

## ファイル構成

```
skills/schedule-optimizer/
├── SKILL.md             # このファイル
└── scripts/
    ├── optimizer.py     # メインロジック
    ├── test_optimizer.py
    └── config.json      # 設定（営業時間・バッファルール等）
```

## 使い方

### 1. カレンダーデータを取得する（gogcli）

```bash
GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog calendar events \
  --from 2026-03-10 --to 2026-03-14 \
  --account operator-secondary@example.com \
  --all --json > /tmp/events.json
```

### 2. 候補を生成する

```bash
# テキスト出力（デフォルト）
python3 skills/schedule-optimizer/scripts/optimizer.py \
  --date-range 2026-03-10:2026-03-14 \
  --duration 60 \
  --events-file /tmp/events.json

# メール文面形式
python3 skills/schedule-optimizer/scripts/optimizer.py \
  --date-range 2026-03-10:2026-03-14 \
  --duration 60 \
  --events-file /tmp/events.json \
  --format email

# stdin から読む（パイプ）
cat /tmp/events.json | python3 skills/schedule-optimizer/scripts/optimizer.py \
  --date-range 2026-03-10:2026-03-14 \
  --duration 60

# 午前NG（午後のみ）
python3 skills/schedule-optimizer/scripts/optimizer.py \
  --date-range 2026-03-10:2026-03-14 \
  --duration 60 \
  --events-file /tmp/events.json \
  --avoid-morning
```

### 3. ワンライナー（gogcli + optimizer）

```bash
GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog calendar events \
  --from 2026-03-10 --to 2026-03-14 \
  --account operator-secondary@example.com \
  --all --json \
| python3 skills/schedule-optimizer/scripts/optimizer.py \
  --date-range 2026-03-10:2026-03-14 \
  --duration 60 \
  --avoid-morning \
  --format email
```

## オプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `--date-range START:END` | 対象期間 (ISO 8601) | 必須 |
| `--duration N` | 1コマの分数 | 60 |
| `--events-file PATH` | イベントJSONファイル | stdin |
| `--avoid-morning` | 午前NG（13:00以降のみ） | config依存 |
| `--format text\|email\|json` | 出力形式 | text |
| `--config PATH` | 設定ファイルパス | scripts/config.json |

## 機能詳細

### バッファルール（config.json）

`buffer_rules` にキーワードを登録すると、そのキーワードを含む予定の前後に移動バッファが自動付与される。

```json
"buffer_rules": [
  {"keyword": "銀行", "before_minutes": 60, "after_minutes": 60},
  {"keyword": "bank", "before_minutes": 60, "after_minutes": 60}
]
```

→ 「銀行 打ち合わせ 14:00-15:00」は **13:00-16:00** がブロックされる。

### 午前NG（avoid_morning）

`config.json` で `"avoid_morning": true` に設定、または CLI で `--avoid-morning` を指定すると、13:00以降のスロットのみ返す。

### 出力形式

**text（デフォルト）:**
```
3/10（火）13:00-14:00
3/10（火）14:00-15:00
3/11（水）13:00-14:00
```

**email:**
```
ご都合のよろしい日程をご確認ください。

  1. 3/10（火）13:00-14:00
  2. 3/10（火）14:00-15:00
  3. 3/11（水）13:00-14:00

どうぞよろしくお願いいたします。
```

**json:**
```json
[
  {"start": "2026-03-10T13:00:00+09:00", "end": "2026-03-10T14:00:00+09:00"},
  ...
]
```

## テスト実行

```bash
cd /workspace
python3 -m pytest skills/schedule-optimizer/scripts/test_optimizer.py -v
```

## 技術仕様

- Python 3.10+ 標準ライブラリのみ（外部パッケージなし）
- gogcli の JSON 出力形式（`dateTime` / `date` フィールド）に対応
- タイムゾーン: Asia/Tokyo（zoneinfo モジュール使用）
- 土日除外・全日イベントのブロック対応
