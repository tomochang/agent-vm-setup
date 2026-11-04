---
name: mail
description: Gmail未読メールを分類・返信案作成・送信し、後続タスクまで完遂する（3層アーキテクチャ）
---

# /mail - Gmail返信アシスタント

未読メールを自動分類し、不要メールはアーカイブ、会議情報はカレンダーと照合、要返信メールは返信案を作成・送信する。

## コマンド

```
/mail              # 未読チェック → トリアージ → 下書き生成
/mail check        # 同上
/mail triage       # 同上
/mail send <to> <subject> <body>  # 送信（検証＋後続タスク自動実行）
/mail draft <messageId>           # 下書き用コンテキスト収集
/mail read <messageId>            # メール本文を読む
/mail status       # 現在のトリアージファイルのステータス表示
```

## アーキテクチャ（3層）

```
┌─────────────────────────────────────────────┐
│ スキル (SKILL.md)                            │
│ - 判断ルール（トリアージ分類、トーン選択）      │
│ - 返信ポリシー、送信後チェックリスト           │
├─────────────────────────────────────────────┤
│ プログラム (scripts/)                         │
│ - mail-draft.sh  → コンテキスト強制収集        │
│ - mail-send.sh   → 送信+検証+ステータス更新    │
├─────────────────────────────────────────────┤
│ データ (private/drafts/)                      │
│ - トリアージファイル（ステータス+後続タスクフラグ）│
│ - private/people/P-XXXX.md（人物コンテキスト）    │
│ - memory/YYYY-MM-DD.md（送信ログ）             │
└─────────────────────────────────────────────┘
```

**原則: スキルだけに頼らない。プログラムとデータで担保する。**

## 環境

- **ツール**: `gog` CLI（gogcli）
- **アカウント**: `operator-secondary@example.com`
- **VPS実行**: `GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog <cmd> --account operator-secondary@example.com`
- **スクリプト**: `scripts/mail-draft.sh`, `scripts/mail-send.sh`
- **時刻**: すべてJST表記（UTC禁止）

---

## 処理フロー

### Phase 1: メール取得＋トリアージ

**検索は `is:unread` ではなく時間ベース。既読/未読に依存しない。**

```bash
# 1st: 社内・重要メール（サポート除外）
GOG_KEYRING_PASSWORD=$GOG_KEYRING_PASSWORD gog gmail search \
  "newer_than:1d -label:OPERATOR-COMPANY-Support -category:promotions -category:social -category:forums -category:updates -in:trash" \
  --max 30 --json --account operator-secondary@example.com

# 2nd: 必要に応じて特定送信者や期間を追加検索
```

#### 既存トリアージファイル確認（必須）

新着取得前に `private/drafts/` 配下に別セッションで作られたファイルがないか確認：
```bash
ls -lt private/drafts/*mail* 2>/dev/null
```
→ 既存ファイルがあればマージする。重複対応を防ぐ。

#### 分類

| カテゴリ            | 条件                                                                      | アクション                           |
| ------------------- | ------------------------------------------------------------------------- | ------------------------------------ |
| **skip**            | noreply, notification, alert, 自動送信、Slack/GitHub通知、OPERATOR-COMPANYサポート | 無視（サポートはcronで自動削除済み） |
| **info_only**       | CCで受信、社内共有、レシート/領収書                                       | サマリー表示のみ                     |
| **meeting_info**    | 会議招待、日程確定通知、場所・リンク共有                                  | カレンダー照合＆更新 + **todo登録**  |
| **action_required** | 直接宛先、質問・依頼を含む、日程調整                                      | 返信案作成 + **todo登録**            |

### skip対象

- From に `noreply`, `no-reply`, `notification`, `alert` を含む
- From に `@github.com`, `@slack.com`, `@jira`, `@notion.so` を含む
- From が `@operator-company.example`（OPERATOR-COMPANY関連：support, cs等）
- From が `yads-system-info@`、`@shi-harai.com`、`@onlystory.co.jp`
- Subject に `[GitHub]`, `[Slack]`, `[Jira]` を含む


### ChatGPT定期 Inbox Cleanup の扱い

`operator@example.com` の定期 Inbox Cleanup では、`docs/agent-rules/workflows.md#inbox-cleanup-定期実行` を正とする。

- 明確な低価値メールの **Archive は、メールごとのCase作成・事前Git commitなしで直接実行してよい**。
- Archive は可逆な受信箱整理として standing authorization 済み。Delete/Trashや送信系操作まで拡張しない。
- 要対応通知を出す前に、repo の最新状態（`private/todo.md`、`private/inbox_action_items/`、直近commit、当日/前日memory、関連SSoT）で既対応か確認する。既対応なら再通知しない。
- scheduled/background実行で新規要対応を発見した場合は、`private/todo.md` を書き換えず、`private/inbox_action_items/<gmail-message-id>.json` を1メール1ファイルでcreateする。active項目はTodoと同格に扱い、二重転記しない。後続runで完了証跡が取れたらその小ファイルだけresolvedへ更新する。
- Gmail categoryだけで判断せず本文を読む。曖昧なら受信箱に残す。
- Archive後は可能なら再読でINBOXラベル消失を確認し、失敗を成功扱いしない。

### meeting_info 自動処理

会議情報を含むメールを検知 → カレンダー照合 → 不足情報を補完。

検知キーワード:
```
Teams, Zoom, Meet, WebEx, 会議リンク, 参加URL, 招待,
場所:, 会議室, ビル, 階, .ics, invite.ics
```

処理: 既存イベント特定 → リンク/場所を補完 → 完了後アーカイブ

#### トリアージファイル出力

`private/drafts/mail-replies-YYYY-MM-DD.md` に以下を生成：

```markdown
# メール返信 — YYYY-MM-DD

## 送信フロー（厳守）
1. `mail-draft.sh <messageId>` でコンテキスト収集
2. 下書き作成・承認
3. `mail-send.sh <to> <subject> <body> [--reply-to <messageId>]` で送信
4. 後続タスクフラグをすべて✅にする
※ すべて✅になるまで次に進まない

## ステータス

| # | 相手 | messageId | 送信 | status | cal | rel | mem | 送信日時 |
|---|------|-----------|------|--------|-----|-----|-----|---------|
| 1 | 松野陽子 | abc123 | ❌ | - | - | - | - | |
```

### Phase 1.5: todoへのタスク登録（トリアージ直後に必ず実行）

**メールはタスク発見の入口。todoがSOT（Source of Truth）。**

通常の対話型 `/mail` で action_required / meeting_info のメールを処理する場合は、トリアージ直後に `private/todo.md` にタスクとして登録する。**ChatGPT定期 Inbox Cleanup は例外で、上記の `private/inbox_action_items/<gmail-message-id>.json` を正本とし、`todo.md` へ二重転記しない。**

```markdown
# 登録フォーマット
| ステータス | 項目 | 担当 |
| 要返信 | **〇〇さん — 件名要約** — MM/DD受信。要点。messageId: xxx | 相手名 or the operator |
```

**ルール:**
- 既にtodoに同じ件が存在する場合は重複登録しない（messageIdかキーワードで突合）
- 返信送信済みになったら「返信待ち」に変更
- 完了したら打ち消し線
- **通常の対話型 `/mail` ではtodoに書かないトリアージは未完了扱い。定期Inbox Cleanupでは action-item JSON のremote保存・再読が同じ完了条件。**

### Phase 2: 下書き生成

**必ず `mail-draft.sh` を実行してから下書きを書く。**

```bash
bash scripts/mail-draft.sh <messageId>
```

出力内容:
1. **private/people/P-XXXX.md** の該当人物ファイル
2. **メール本文**（全文）
3. **スレッド内の過去やり取り**
4. **カレンダー空き状況**（日程調整キーワード検知時）

→ この出力を読んでから下書きを作成する。出力なしで下書きを書くことは禁止。

#### 下書きルール

- 署名: `the operator`
- トーン: SOUL.md「対・外部（ビジネス）」参照
  - 情熱的、仕事ができる、ポジティブ、謙虚、丁寧
- 日程調整: 平日9-18時のみ、土日除外
- 銀行系: 前後1時間の移動バッファ考慮
- **不要な謝罪を入れない**
- **返信は必ず `--reply-to-message-id` でスレッド維持**

### Phase 3: 送信

```bash
bash scripts/mail-send.sh <to> <subject> <body> [--reply-to <messageId>]
```

スクリプトが自動実行すること:
1. 送信（reply-to指定時はスレッド維持）
2. **レスポンス検証**（送信成功確認 + エラーチェック）
3. **ステータスファイル自動更新**
4. 後続タスクリスト表示

### Phase 4: 後続タスク

送信成功後、以下をすべて完了する。ステータステーブルの各フラグを✅にする。

人物の解決、interactionsへの重複なし追記、`private/people/P-XXXX.md`の`last_contact`・`updated`・`next_action`および必要な要約、Todoとの整合は `docs/agent-rules/relationship-sync.md` を正とする。定型返信では本文要約を増やさず、frontmatterとinteractionsだけ更新する。

| タスク | 内容 | 自動/手動 |
|--------|------|-----------|
| **status** | ステータステーブル更新 | 🤖 mail-send.sh が自動 |
| **cal** | カレンダー仮押さえ（日程関連の場合） | ✋ 手動 |
| **rel** | interactions追記 + 人物ファイル・next_action更新 | ✋ 手動 |
| **mem** | memory/YYYY-MM-DD.md 送信記録 | ✋ 手動 |

**全フラグが✅になるまで次のメッセージに進まない。**

### Phase 5: エラー処理

- 送信失敗 → mail-send.sh がエラー出力 → リカバリ試行
- リカバリ成功 → **Telegramに「送信完了しました」と即座に報告**

---

## 出力フォーマット例

```
## 未読メール確認結果

### スキップ (3件) → 自動アーカイブ済み
- バクラク受領 <no-reply@...> - 書類の送信を受け付けました

### 情報のみ (2件)
- Anthropic <invoice@...> - Your receipt #2718-8582

### 要返信 (2件)

#### 1. 松野陽子 <yoko@helixes.co>
**件名**: 不正利用の疑いの件
**受信**: 2026-02-03 20:07 JST
**要点**: [メール内容の要約]

**返信案**:
お世話になっております。the operatorです。
[返信本文]
the operator

→ [送信] [編集] [スキップ]
```

---

## 関連ファイル

| ファイル | 用途 |
|---------|------|
| `scripts/mail-draft.sh` | 下書き用コンテキスト強制収集 |
| `scripts/mail-send.sh` | 送信+検証+ステータス更新 |
| `private/people/INDEX.md`, `private/people/P-XXXX.md` | 人物解決・人物コンテキスト |
| `docs/agent-rules/relationship-sync.md` | 送受信後のCRM同期手順 |
| `private/drafts/mail-replies-*.md` | トリアージ＋ステータス管理 |
| `SOUL.md` | 返信トーン設定 |
| `TOOLS.md` | gog CLIリファレンス |
