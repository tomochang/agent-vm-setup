---
name: cross-check
description: Codexペインにコードレビューを依頼し、フィードバックを取得する
---

# /cross-check - Codexクロスチェックレビュー

## 概要

tmux経由でCodexペインにコードレビューを依頼し、フィードバックを取得してユーザーに報告する。

## 使用方法

```
/cross-check              # staged + unstaged の全差分をレビュー依頼
/cross-check <file>...    # 指定ファイルのみレビュー依頼
```

**引数:** $ARGUMENTS

---

## ワークフロー

### Step 1: Codexペイン検出

```bash
CODEX_PANE=$("$HOME/records repo/scripts/tmux-crosscheck.sh" find-codex)
```

Codexペインが見つからない場合:

- ユーザーに報告: 「Codexペインが見つかりません。`C-a M-x` でクロスチェックレイアウトを起動するか、別ペインで `codex` を起動してください。」
- 処理を中断

### Step 2: 差分収集

引数がある場合は指定ファイルのみ、なければ全差分を収集:

```bash
# 引数ありの場合
git diff -- <files> > /tmp/crosscheck-diff.txt
git diff --cached -- <files> >> /tmp/crosscheck-diff.txt

# 引数なしの場合
git diff > /tmp/crosscheck-diff.txt
git diff --cached >> /tmp/crosscheck-diff.txt
```

**差分が空の場合:**

- ユーザーに報告: 「差分がありません。変更を加えてから再実行してください。」
- 処理を中断

**差分が500行を超える場合:**

- 差分を `git diff --stat` のサマリー + 最初の500行に切り詰める
- ユーザーに警告: 「差分が大きいため、最初の500行のみ送信します。」

### Step 3: レビュー依頼送信

差分ファイルのパスと review プロンプトをCodexペインに送信:

```bash
"$HOME/records repo/scripts/tmux-crosscheck.sh" send "$CODEX_PANE" "/prompts:review

以下の差分をレビューしてください:

$(cat /tmp/crosscheck-diff.txt)"
```

**注意:** テキストが長すぎる場合（4000文字超）はファイルパス参照に切り替える:

```bash
"$HOME/records repo/scripts/tmux-crosscheck.sh" send "$CODEX_PANE" "/prompts:review

以下のファイルの差分をレビューしてください。差分ファイル: /tmp/crosscheck-diff.txt

差分の概要:
$(git diff --stat)"
```

### Step 4: 結果取得

Codexの処理完了を待ち、出力をキャプチャする:

1. **待機**: 15秒待つ（Codexの処理時間）
2. **キャプチャ**: `tmux-crosscheck.sh capture "$CODEX_PANE" 200` で最新200行を取得
3. **結果解析**: キャプチャした出力からレビュー結果を抽出
4. **ユーザーに報告**: レビュー結果を整形して表示

```bash
sleep 15
REVIEW=$("$HOME/records repo/scripts/tmux-crosscheck.sh" capture "$CODEX_PANE" 200)
```

結果にレビューフォーマット（`## 概要`, `## 問題点`, `## 総合判定`）が含まれない場合:

- 追加で15秒待ってリトライ（最大2回）
- それでも取得できない場合はキャプチャ全文をそのまま表示

### Step 5: ユーザーに報告

レビュー結果を表示し、対応を選択:

- **総合判定が APPROVE**: 「Codexのレビューで問題なしです。」
- **総合判定が REQUEST_CHANGES**: CRITICALとWARNINGを一覧で表示し、修正対応するか確認
- **総合判定が COMMENT**: INFOレベルの指摘を表示

---

## 前提条件

- tmuxセッション内で実行されていること
- 別ペインでCodexが起動済みであること
- gitリポジトリ内で実行されていること（差分取得のため）
