---
name: docusign-send
description: DocuSignテンプレートを使ったエンベロープの送信・追跡を自動化する
---

# /docusign-send - DocuSign 自動送信アシスタント

DocuSign テンプレートを使い、契約書エンベロープの作成・送信・ステータス追跡を行う。

## コマンド

\`\`\`
/docusign-send                          # テンプレート一覧表示 → 送信フロー
/docusign-send list                     # ローカルテンプレート一覧
/docusign-send list --remote            # DocuSign API からテンプレート一覧取得
/docusign-send status <envelope-id>     # エンベロープのステータス確認
\`\`\`

## アーキテクチャ（3層）

\`\`\`
┌─────────────────────────────────────────────┐
│ スキル (SKILL.md)                            │
│ - 送信判断ルール、確認フロー                  │
│ - 送信ポリシー、送信後チェックリスト           │
├─────────────────────────────────────────────┤
│ プログラム (src/)                             │
│ - docusign-client.js → API操作（認証・送信）   │
├─────────────────────────────────────────────┤
│ データ (config/ + logs/)                      │
│ - templates.json（テンプレート定義）           │
│ - send-log.md（送信履歴）                     │
│ - config/originals/（PDF原本）                │
└─────────────────────────────────────────────┘
\`\`\`

## 環境

- **SDK**: \`docusign-esign\` (npm)
- **認証**: JWT Grant（RSA秘密鍵）
- **環境変数**: \`projects/docusign-automation/config/.env\` から読み込み
- **スクリプト**: \`projects/docusign-automation/src/docusign-client.js\`
- **テンプレート定義**: \`projects/docusign-automation/config/templates.json\`
- **サンドボックス**: \`demo.docusign.net\`（テスト用、透かし入り）
- **本番**: 環境変数で \`DOCUSIGN_BASE_PATH\` を切り替え

---

## 処理フロー

### Phase 1: 情報収集（送信前）

1. ユーザーから以下を収集:
   - **テンプレート名**（必須）— templates.json のキーから選択
   - **受信者メール**（必須）
   - **受信者氏名**（必須）
   - **CC**（任意）
   - **件名カスタマイズ**（任意、デフォルトはテンプレート定義から）

2. テンプレート詳細を確認:
\`\`\`bash
source projects/docusign-automation/config/.env && \\
  node projects/docusign-automation/src/docusign-client.js show-template --name "<テンプレート名>"
\`\`\`

3. **dry-run で内容確認**:
\`\`\`bash
source projects/docusign-automation/config/.env && \\
  node projects/docusign-automation/src/docusign-client.js send --dry-run \\
    --template "<テンプレート名>" \\
    --recipient-email "<メール>" \\
    --recipient-name "<氏名>"
\`\`\`

4. dry-run の結果をユーザーに提示し、**明示的な送信承認を得る**

### Phase 2: 送信

⚠️ **ユーザーの明示的な承認なしに送信してはならない（HIGH リスクアクション）**

\`\`\`bash
source projects/docusign-automation/config/.env && \\
  node projects/docusign-automation/src/docusign-client.js send \\
    --template "<テンプレート名>" \\
    --recipient-email "<メール>" \\
    --recipient-name "<氏名>" \\
    --cc "<CC1>,<CC2>"
\`\`\`

結果の \`envelopeId\` を控える。

### Phase 3: 送信後タスク（自動実行）

送信完了後、**確認を挟まず即座に**以下を実行:

1. **送信ログ更新** — \`projects/docusign-automation/logs/send-log.md\` に記録
2. **todo.md 更新** — アクション待ちテーブルに「署名待ち: <相手名> <テンプレート名>」を追加
3. **commit & push** — \`cd the records checkout && git add -A && git commit -m "docusign: send <テンプレート名> to <相手名>" && python3 scripts/records_gate.py push\`

---

## 送信ポリシー

- **送信時間帯**: 総務部の標準送付時間帯 17:00-18:00 JST を推奨（厳密な制約ではない）
- **dry-run 必須**: 初回送信は必ず \`--dry-run\` で確認してからユーザー承認を得る
- **PII 禁止**: ログやコミットメッセージに個人メールアドレスを含めない。氏名・テンプレート名のみ記録
- **本番切り替え**: サンドボックスでのテスト完了後、環境変数を本番に切り替える

## やってはいけないこと

- ユーザー承認なしでの送信（dry-run 以外の \`send\` コマンド実行）
- ログやドキュメントへの受信者メールアドレスの記載
- サンドボックスと本番の混同（\`DOCUSIGN_BASE_PATH\` を必ず確認）

## ステータス確認

\`\`\`bash
source projects/docusign-automation/config/.env && \\
  node projects/docusign-automation/src/docusign-client.js status --envelope-id "<ENVELOPE_ID>"
\`\`\`

ステータス: \`sent\` → \`delivered\` → \`completed\`（署名完了）
