---
name: team-manage
description: 5エージェントチームのタスク管理・進捗監視・クロスレビュー・品質管理を行う
---

# /team-manage — チームマネジメント

## 概要

5エージェントチーム（Manager + Claude×2 + Codex×2）のタスク管理を行う。
ユーザーの要求をサブタスクに分解し、各実装者に割り振り、進捗を監視してクロスレビューまで実施する。

## 使用方法

```
/team-manage <ユーザーの要求>
```

**引数:** $ARGUMENTS

---

## リポジトリ範囲の制約（最重要）

- **編集・生成・テストは `research/neobank-ui-design/` 配下のみ**
- 全タスク送信時に `cd research/neobank-ui-design && pwd && git status` を先頭に含める
- 範囲外の編集を検知したら即停止して差し戻し

## ワークフロー

### Step 1: チーム状態確認

```bash
$HOME/records/scripts/tmux-team.sh status
```

全ペインの状態を確認し、利用可能な実装者を特定する。

### Step 2: タスク分解

ユーザーの要求を独立したサブタスクに分解する:

- ファイル競合が起きないように分割
- Claude向け（フロント/UX/画面遷移/文言）とCodex向け（バックエンド/DB/状態遷移/テスト）に分類
- 依存関係を明示
- **優先順:** TOP画面 → 振込（単発） → 承認 → 残高証明書

### Step 3: タスク割り振り

空いている実装者に `assign` でタスクを送信。**必ず `pwd && git status` チェックを含める:**

```bash
$HOME/records/scripts/tmux-team.sh assign cl1 "cd $HOME/records/research/neobank-ui-design && pwd && git status && <タスク内容>"
$HOME/records/scripts/tmux-team.sh assign cx1 "cd $HOME/records/research/neobank-ui-design && pwd && git status && <タスク内容>"
```

### Step 4: 進捗監視

定期的に `capture-all` で全ペインの出力を確認:

```bash
$HOME/records/scripts/tmux-team.sh capture-all 50
```

- `DONE:` を検出 → クロスレビューへ
- `BLOCKED:` を検出 → 原因分析・ヒント送信
- 無応答 → `compact` or `clear` + タスク再送信

### Step 5: クロスレビュー

```bash
# Claude実装 → Codexレビュー
$HOME/records/scripts/tmux-team.sh review-route cl1 cx1

# Codex実装 → Claudeレビュー
$HOME/records/scripts/tmux-team.sh review-route cx1 cl2
```

### Step 6: 完了報告

全サブタスクのレビューが APPROVE になったら:

- `git diff --stat` で `research/neobank-ui-design/` 配下以外に変更がないことを確認
- テスト実行（Unit/Contract + 最短E2E）
- 変更ファイル一覧とサマリーをユーザーに報告
- 必要に応じて git commit を指示

---

## テスト方針

- Unit/Contract厚め + E2E極小
- PR前に「Unit/Contract + 最短E2E」だけ通す
- flakeは即修正 or 一時無効化

## 前提条件

- `team` tmuxセッションが起動済みであること
- 5ペイン（mgr, cl1, cl2, cx1, cx2）が存在すること
- `scripts/tmux-team.sh` が実行可能であること
- 作業指示書: `research/neobank-ui-design/docs/plans/ai-work-instructions-2026-02-19.md`
