---
name: today
description: 朝のブリーフィング — メール・LINE・カレンダーを並列取得し、トリアージ＋返信処理まで完遂する
---

# /today — Morning Briefing & Triage

## Overview

メール、LINE、カレンダー/todoを取得し、今日のブリーフィングを生成。
action_required項目は返信ドラフト→送信→後続タスクまで処理する。

## CLI Contract

機械実行・agent連携では [scripts/today](/tmp/today-cli-progress/scripts/today) を使う。

```bash
python3 scripts/today run --json
python3 scripts/today doctor --json
```

非TTYでは `run` / `doctor` とも JSON mode が自動有効化される。

`today run` の返却 schema:

```json
{
  "ok": true,
  "partial": false,
  "summary": {
    "mail_unread": 0,
    "line_unread": 0,
    "calendar_events_today": 0,
    "drafts_created": 0,
    "messages_sent": 0
  },
  "actions": [],
  "pending": [],
  "warnings": [],
  "errors": []
}
```

エラーは `code + message` で返る。現時点の主要 code:

- `gmail_unavailable`
- `calendar_unavailable`
- `line_unavailable`
- `partial_fetch`
- `auth_error`

exit code:

- `0`: success
- `2`: partial failure
- `1`: doctor fail または run hard failure

---

## Step 0: コンテキスト復元

```bash
# private/配下の人物・予定情報を先に読む
cat private/INDEX.md
cat private/todo.md | head -100
```

---

## Step 1: 並列データ取得

### 1-A: メール取得＋分類

**検索は時間ベース。`is:unread` は使わない。既読/未読に依存しない。**
**サポートメールはcronで自動削除済み（`scripts/gmail/trash-support-mail.sh`）**

```bash
# 社内・重要メール（サポート・プロモ・フォーラム除外、直近24h）
GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog gmail search \
  "newer_than:1d -label:OPERATOR-COMPANY-Support -category:promotions -category:social -category:forums -category:updates -in:trash" \
  --max 30 --account operator-secondary@example.com

GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog gmail search \
  "newer_than:1d" --max 10 --account operator@example.com 2>/dev/null || true
```

**分類ルール（優先順）:**

| カテゴリ | 条件 | アクション |
|----------|------|-----------|
| **skip** | noreply/notification/GitHub/Slack/Jira、OPERATOR-COMPANY Support（cron自動削除済み） | 無視（報告不要） |
| **meeting_info** | Zoom/Teams/Meet URL + 日時 | カレンダー突合 + **todo登録** |
| **action_required** | 直接宛先 + 質問/依頼 | 返信案作成 + **todo登録** |
| **info_only** | CC、レシート、通知系 | サマリー表示のみ |

### 1-B: LINE・Messenger取得＋流れ判定（Beeper Desktop API、2026-10-05〜）

`python3 scripts/today run --json` の `conversations`（直近7日・各チャット直近10件、LINE+Messenger）を読み、**最新1件ではなく流れで**4区分に分ける。基準は memory `reply-needed-criteria`:

| 区分 | 条件 |
|---|---|
| 要返信 | 相手が質問・依頼・呼びかけを送りthe operator未反応。大人数グループでも名前で呼ばれた質問・依頼。質問のない近況報告は自動で要返信にしない。Lenaさんは対象外（本人指示） |
| 自分の宿題 | the operatorが「確認します」「聞いてみます」等と約束して未履行 |
| 相手待ち | the operatorが最後に依頼・質問を送った |
| 完了 | the operatorが始めたやり取りへの締めの返し、雑談の自然な終わり |

- `actions` の line/messenger（最新1件ルール）は参考。食い違えば `conversations` の判定を優先
- Beeper Desktop が起動していないと取得できない（Messenger は error 表示）
- 全アカウントの新着はまず差分を読む: `python3 scripts/beeper_sync.py`（前回チェックポイント以降＋pending。全件は `--all` を指定した時だけ）。exit 3 / `complete: false` は未完了なので該当アカウントを報告する
- 個別スレッドをもっと遡る: `python3 scripts/beeper_sync.py --thread <chat_id> --limit 30`（IDは `--find "<名前>"`。複数候補なら推測で選ばない）
- 振り返しまで終えたら、残る要返信・相手待ちを `--pending-add <chat_id>`、片付いたものを `--pending-clear <chat_id>` し、最後に `--checkpoint`。途中で止めたら実行しない

### 1-C: カレンダー + Todo

```bash
GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog calendar events \
  --today --all --max 30 --account operator-secondary@example.com
```

---

## Step 2: ブリーフィング生成

以下のフォーマットで出力：

```
## 📋 Today — YYYY-MM-DD (曜日)

### スケジュール (N件)

| 時間 | 予定 | 場所 |
|------|------|------|

### メール

#### Skipped (N) → 無視
#### Info Only (N)
#### Action Required (N)
1. 送信者 — 件名 — 要約

### LINE

#### 要返信 (N)
1. 名前 — 最終メッセージ要約
#### 確認済み (N)

### 今日の優先順位（todo + メッセージ）
P1（N）
1. タイトル — 理由（期限超過5日・hard 等）
P2（N）
1. ...
P3（上位5件 / 全N件）
待ち（N）: 名前, 名前, ...

---

ブリーフィング完了。N件のaction_requiredを処理します。
```

`今日の優先順位` は `python3 scripts/today run --json` の `priorities` を土台にする。並べ方・調整ルールは `.claude/commands/today.md` の「今日の優先順位」。

---

## Step 2.5: todoへのタスク登録（ブリーフィング直後に必ず実行）

**メール・LINEはタスク発見の入口。todoがSOT。**

action_required / meeting_info の項目を `private/todo.md` に登録する。

- 既にtodoに同じ件が存在する場合は重複登録しない
- 返信送信済みになったら「返信待ち」に変更
- **todoに書かないトリアージは未完了扱い**

## Step 3: action_required処理

### 3.1 コンテキスト収集

**メール:** `private/people/INDEX.md`で送信者を解決し、該当する`private/people/P-XXXX.md`を読む
**LINE/Messenger:** `scripts/beeper_sync.py --thread` でスレッドを読み、`private/people/` で人物を解決する（旧 `line-draft.sh` はMatrix前提で停止中）

### 3.2 日程調整検出

以下のキーワードを検出したらカレンダー空き確認：
```
日程, 予定, 空いて, いつ, スケジュール, MTG, 打ち合わせ, ご飯, 飲み
```

```bash
GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog calendar freebusy \
  --start "YYYY-MM-DDT00:00:00+09:00" --end "YYYY-MM-DDT00:00:00+09:00" \
  --account operator-secondary@example.com
```

### 3.3 返信ドラフト作成（comms-draft品質ゲート必須）

返信案を作成したら、以下の構造化JSONを `/tmp/comms-draft.json` に書き出す:

```json
{
  "recipient": "受け手の名前と役職",
  "recipient_context": "この件について受け手が知っていること・知らないこと",
  "channel": "slack or email or line",
  "items": [
    {
      "content": "依頼・伝達の本文",
      "reason": "なぜこれが必要か（受け手が理解できる背景）",
      "evidence": "この文の根拠（確認済みのソース。未確認なら null）"
    }
  ],
  "draft": "最終的な送信文面"
}
```

**品質チェック実行:**

```bash
python3 scripts/comms-check.py /tmp/comms-draft.json
```

- **PASS** → ドラフトをユーザーに提示
- **FAIL** → 指摘事項を修正してJSONを書き直し、再実行。PASSするまで提示しない

**なぜ:** [odysseus#22](https://github.com/upsidr/odysseus/issues/22) — 事実未確認のまま返信を生成→誤情報送信。evidence=nullのitemは事実確認してからdraftに含める。

**メール固有:**
- 署名: 「the operator」
- トーン: SOUL.md「対・外部（ビジネス）」参照
- 銀行系: 前後1h移動バッファ考慮
- **必ず `--reply-to-message-id` で返信**

**LINE固有:**
- `line-draft.sh` 実行必須（SKILL.md参照）
- `line-review.sh` でPASS必須
- voice examples参照

### 3.4 ユーザーに提示

各action_required項目について：
- 元メッセージ要約
- 返信ドラフト
- 送信するか確認

### 3.5 送信

**メール:**
```bash
GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog gmail send \
  --reply-to-message-id "<messageId>" \
  --to "<recipient>" --body "<reply>" \
  --account operator-secondary@example.com
```

**LINE/Messenger:** Beeper Desktop APIのread/write接続が有効な場合、本人が宛先と本文を承認した後に `POST /v1/chats/<id>/messages`（JSON `{ "text": "..." }`）で送信できる。accountID・チャット名・直近履歴を照合し、送信後は同じチャットの履歴で送信者と本文を再読する。Beeperが利用できない場合は送信できたと扱わず、本文を本人へ提示する。

---

## Step 4: 後続タスク（送信ごとに必ず実行）

| # | タスク | 対象 |
|---|--------|------|
| 1 | カレンダー登録/更新 | 日程関連の場合 |
| 2 | People CRM同期 | `docs/agent-rules/relationship-sync.md`に従いinteractions・人物ファイルを更新 |
| 3 | todo.md更新 | 予定変更・タスク追加（P-ID必須） |
| 4 | memory記録 | memory/YYYY-MM-DD.md |

**全項目完了するまで次のメッセージに進まない。**

### P-ID付与（#2, #3で必須）

```bash
# 人物のP-IDを検索
python3 scripts/pid_manager.py lookup "人物名"

# 見つからなければ新規採番
python3 scripts/pid_manager.py next
```

- **人物更新時:** `docs/agent-rules/relationship-sync.md`に従う。新規人物は自動作成せず、the operatorの承認を得る
- **todo更新時:** 人物関連の行に `<!-- P-XXXX -->` を行末に付与
- **両方に同じP-IDを使う。** 片方だけに振らない
- **同姓同名注意:** 名前だけで判断せず、`lookup` で既存エントリを確認してから紐づける

---

## Step 5: git commit

```bash
cd $HOME/workspace && git add -A && \
  git commit -m "today: morning triage" && python3 scripts/records_gate.py push
```

---

## カスタムskipルール

以下の送信者/件名はskip:
- 永山総子さん（西中洲雲母）— 挨拶系
- OPERATOR-COMPANY Support（cs@operator-company.example）
- GitHub/Slack/Jira通知
- 公式LINEアカウント（SKILL.md line参照）

## メール対応メモ

- **午前NGの好み** — 候補提案時は午後以降を優先
- **銀行系** — 前後1h移動バッファ自動追加
- **返信が来てから入れよう、は禁止** — 候補提示時点で[仮]登録
