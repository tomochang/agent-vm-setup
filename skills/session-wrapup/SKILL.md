---
name: session-wrapup
description: セッション終了時の自動処理（commit検出・memory整理・ルール抽出・次回準備）
---

# session-wrapup

セッション終了時に実行する自動処理スキル。

## コマンド

```
/wrapup
/session-wrapup
```

## 機能

| # | 機能 | 説明 |
|---|------|------|
| 1 | **Git status** | `git status --porcelain` + `git log origin/main..HEAD` で未コミット/未プッシュを検出 |
| 2 | **Memory consolidation** | 当日の `memory/YYYY-MM-DD.md` からキーイベントを抽出しサマリーを生成 |
| 3 | **Rule extraction** | ルール/パターン/教訓キーワードを含む行を抽出し AGENTS.md 追記候補として提示 |
| 4 | **Next session prep** | `memory/AGENT_WORK.md` の未完了タスクを整理し次回セッション向けにまとめる |
| 5 | **Session report** | 上記を統合したレポートを stdout に出力 |

## 使い方

エージェントが `/wrapup` または `/session-wrapup` を受け取ったとき、以下を実行する:

```bash
python3 /workspace/skills/session-wrapup/scripts/wrapup.py \
  --workspace /workspace \
  --date YYYY-MM-DD
```

`--date` を省略すると今日の日付が使われる。

## 出力例

```
# セッション終了レポート — 2026-03-07

生成時刻: 2026-03-07 18:45:00
---

## 📦 Git Status

⚠️  未コミットファイル: 2件
  - memory/2026-03-07.md
  - skills/session-wrapup/SKILL.md
⚠️  未プッシュcommit: 1件
  - abc1234 Add session-wrapup skill

## 🧠 Memory Consolidation

## セッションサマリー (2026-03-07)

  1. session-wrapupスキル作成
  2. TDDでテスト全パス

## 📐 Rule Extraction

以下のルール候補をAGENTS.md/SHARED_RULES.mdへの追記を検討:
  > テストを先に書く必須ルール

## 🔜 Next Session Prep

未完了タスク: 1件
  [WIP] 銀行資料作成

---
_次のセッションで `/wrapup` を実行すれば再生成できます。_
```

## ファイル構成

```
skills/session-wrapup/
├── SKILL.md              # このファイル
└── scripts/
    ├── wrapup.py         # メインスクリプト
    └── test_wrapup.py    # pytestテスト (17テスト)
```

## 技術仕様

- Python 3.10+ 標準ライブラリのみ
- `subprocess` で git コマンドを実行
- 各ステップは独立 — エラーが出ても他のステップは継続
- テストは `unittest.mock.patch` でサブプロセスをモック

## テスト実行

```bash
cd /workspace/skills/session-wrapup
python3 -m pytest scripts/test_wrapup.py -v
```
