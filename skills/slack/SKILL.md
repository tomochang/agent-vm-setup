---
name: slack
description: Slackメッセージの確認・分類・返信案作成・送信を行う（slack-mcp-server経由）
---

# /slack - Slackメッセージアシスタント

slack-mcp-server（MCP）経由でOPERATOR-COMPANYワークスペースのメッセージを確認し、分類・返信案作成・送信を行う。

## コマンド

```
/slack              # 未読・メンション確認 → トリアージ → 下書き生成
/slack check        # 同上
/slack send <channel> <message>  # 送信（検証＋後続タスク）
/slack draft <channel>           # 下書き用コンテキスト収集
/slack read <channel>            # 特定チャンネルの最新メッセージを読む
/slack channels     # チャンネル一覧
/slack search <query>  # メッセージ検索
/slack status       # トリアージファイルのステータス表示
```

## アーキテクチャ（3層）

```
┌─────────────────────────────────────────────┐
│ スキル (SKILL.md)                            │
│ - 判断ルール（トリアージ分類、トーン選択）      │
│ - チャンネル別送信ポリシー                     │
├─────────────────────────────────────────────┤
│ プログラム (scripts/)                         │
│ - slack-draft.sh  → コンテキスト強制収集       │
│ - slack-send.sh   → 送信+検証+ステータス更新   │
├─────────────────────────────────────────────┤
│ データ (private/drafts/)                      │
│ - トリアージファイル（ステータス+後続タスクフラグ）│
│ - private/people/P-XXXX.md（人物コンテキスト）    │
│ - memory/YYYY-MM-DD.md（送信ログ）             │
└─────────────────────────────────────────────┘
```

**原則: スキルだけに頼らない。プログラムとデータで担保する。**

## 環境

- **ツール**: slack-mcp-server（MCP経由）
- **ワークスペース**: OPERATOR-COMPANY (`<SLACK_WORKSPACE_ID>`)
- **認証**: ブラウザセッショントークン（xoxc/xoxd）
- **スクリプト**: `scripts/slack-draft.sh`, `scripts/slack-send.sh`
- **時刻**: すべてJST表記（UTC禁止）

### MCP利用可能ツール

- `conversations_list` — チャンネル・DM一覧
- `conversations_history` — メッセージ履歴取得
- `conversations_add_message` — メッセージ送信
- `users_list` — ユーザー一覧
- `search_messages` — メッセージ検索

---

## 処理フロー

### Phase 1: 未読取得＋トリアージ

MCP経由で未読・メンションを取得:
1. `search_messages` で `from:me` 以外の直近メッセージ確認
2. メンション・DM・リアクション要求を特定

#### 既存トリアージファイル確認（必須）

```bash
ls -lt private/drafts/*slack* 2>/dev/null
```

#### 分類

| カテゴリ            | 条件                                       | アクション         |
| ------------------- | ------------------------------------------ | ------------------ |
| **skip**            | bot通知、自動アラート、CI/CD結果           | 無視               |
| **info_only**       | 一般チャンネルの雑談、全体アナウンス       | サマリー表示のみ   |
| **action_required** | DMでの質問、メンション、承認要求、日程調整 | 返信案作成         |

#### skip対象（bot / 自動通知）

```
GitHub Bot, Jira Bot, PagerDuty, CircleCI, Sentry,
Notion Bot, Google Calendar, Zapier, Workflow Builder
```

#### トリアージファイル出力

`private/drafts/slack-replies-YYYY-MM-DD.md` に以下を生成：

```markdown
# Slack返信 — YYYY-MM-DD

## 送信フロー（厳守）
1. `slack-draft.sh <channelId>` でコンテキスト収集
2. 下書き作成・承認
3. `slack-send.sh <channelId> <メッセージ>` で送信
4. 後続タスクフラグをすべて✅にする

## ステータス

| # | チャンネル/相手 | channelId | 送信 | status | rel | mem | 送信日時 |
|---|----------------|-----------|------|--------|-----|-----|---------|
| 1 | @tanaka | C012345 | ❌ | - | - | - | |
```

### Phase 2: 下書き生成

**必ず `slack-draft.sh` を実行してから下書きを書く。**

```bash
bash scripts/slack-draft.sh <channelId>
```

出力内容:
1. **private/people/P-XXXX.md** の該当人物ファイル（DMの場合）
2. **チャンネル履歴** 直近20件（JST表記）
3. **the operatorの文体サンプル** 同チャンネル内の過去送信

→ この出力を読んでから下書きを作成する。出力なしで下書きを書くことは禁止。

#### 下書きルール

- トーン: SOUL.md「対・外部（ビジネス）」参照（社内メンバー向け）
  - ただしSlackはメールより少しカジュアルでOK
  - 絵文字リアクション活用（👍✅🙏 など）
- **スレッド返信を優先**（チャンネルを汚さない）
- **不要な謝罪を入れない**

### Phase 3: 送信

```bash
bash scripts/slack-send.sh <channelId> <メッセージ> [--thread <threadTs>]
```

スクリプトが自動実行すること:
1. MCP経由でメッセージ送信
2. **レスポンス検証**（ok: true確認 + エラーチェック）
3. **ステータスファイル自動更新**
4. 後続タスクリスト表示

### Phase 4: 後続タスク

| タスク | 内容 | 自動/手動 |
|--------|------|-----------|
| **status** | ステータステーブル更新 | 🤖 slack-send.sh が自動 |
| **rel** | `relationship-sync.md`に従いinteractions・人物ファイルを同期 | ✋ 手動 |
| **mem** | memory/YYYY-MM-DD.md 送信記録 | ✋ 手動 |

**全フラグが✅になるまで次のメッセージに進まない。**

---

## ⚠️ チャンネル送信ポリシー（厳守）

### 送信禁止チャンネル

the operatorの明示的指示がない限り、以下には送信しない:
- `#general`, `#random` 等の全体チャンネル
- 経営・人事系チャンネル
- 顧客対応チャンネル

### 送信可能（承認後）

- DM（個人メッセージ）
- the operatorが参加しているプロジェクトチャンネル（指示があれば）

### 自由に送信可能

- なし（すべてthe operatorの承認が必要）

---

## トークン更新手順

セッショントークンが失効した場合:

1. Chrome で `app.slack.com` を開く
2. DevTools → Console:
   ```javascript
   JSON.parse(localStorage.localConfig_v2).teams[
     document.location.pathname.match(/^\/client\/([A-Z0-9]+)/)[1]
   ].token
   ```
3. DevTools → Application → Cookies → `d` の値をコピー
4. `.mcp.json` の `SLACK_MCP_XOXC_TOKEN` と `SLACK_MCP_XOXD_TOKEN` を更新

---

## 関連ファイル

| ファイル | 用途 |
|---------|------|
| `scripts/slack-draft.sh` | 下書き用コンテキスト強制収集 |
| `scripts/slack-send.sh` | 送信+検証+ステータス更新 |
| `private/people/INDEX.md`, `private/people/P-XXXX.md` | 人物解決・人物コンテキスト |
| `docs/agent-rules/relationship-sync.md` | 送受信後のCRM同期 |
| `private/drafts/slack-replies-*.md` | トリアージ＋ステータス管理 |
| `SOUL.md` | 返信トーン設定 |
| `TOOLS.md` | Slack MCP設定リファレンス |
