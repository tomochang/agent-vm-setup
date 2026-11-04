---
name: cron-optimizer
description: cronジョブの棚卸し・最適化（重複検出・スケジュール集中・不要ジョブ）
---

# cron-optimizer

cronジョブの棚卸し・最適化スキル。**提案のみ。自動変更なし。**

## 使い方

```bash
# 基本（重複・スケジュール集中・コメントアウト済みジョブを検出）
python3 scripts/optimizer.py

# 参照スクリプトの存在チェックも行う
python3 scripts/optimizer.py --check-scripts

# OpenClawのcron設定も分析
python3 scripts/optimizer.py --openclaw-config /path/to/openclaw.json

# 集中検出の閾値を変更（デフォルト: 4）
python3 scripts/optimizer.py --threshold 3

# dry-run（デフォルト動作と同じ。提案のみ）
python3 scripts/optimizer.py --dry-run
```

## 機能

| 機能 | 説明 |
|------|------|
| cron一覧取得 | `crontab -l` をパース。スケジュール・コマンド・コメントを分離 |
| 重複検出 | 同一コマンドが複数登録されていないか検出 |
| スケジュール集中検出 | 同時間帯にジョブが集中していないか（デフォルト閾値: 4件） |
| 無効ジョブ検出 | コメントアウト済みcronエントリを検出 |
| スクリプト不在検出 | `--check-scripts` 時、参照ファイルの存在チェック |
| OpenClaw分析 | `openclaw.json` のcronセクションを分析（無効ジョブ等） |
| 最適化提案 | 各問題に対して日本語の具体的な提案を生成 |

## テスト

```bash
cd /workspace/skills/cron-optimizer
python3 -m pytest scripts/test_optimizer.py -v
# 29 tests in 0.09s — 29 passed
```

## ファイル構成

```
skills/cron-optimizer/
├── SKILL.md               # このファイル
└── scripts/
    ├── optimizer.py       # メインスクリプト（Python 3.10+、標準ライブラリのみ）
    └── test_optimizer.py  # テストスイート（29件）
```

## 安全ポリシー

- cronの**変更は一切行わない**。提案のみ。
- エラー時も正常終了（exit code 0）。
- 標準ライブラリのみ（外部依存なし）。
