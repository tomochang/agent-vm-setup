# Skills — rule bodies that load only when the situation matches

A **skill** is a self-contained procedure for one recurring
situation, stored as `skills/<name>/SKILL.md` in the records repo:

```markdown
---
name: verify-todo-outcomes
description: Settle a todo item's outcome against primary sources before changing it.
---

# Body: the procedure, its evidence rules, and its failure cases.
```

The agent searches the skill catalog by name and description, reads
the matching `SKILL.md` **in full**, and follows it. Nothing else
loads. That economy is the point.

## Why not put the rules in the resident file?

The resident instruction file (`AGENTS.md`) is read on every turn.
Two failure modes follow:

- Rules buried in the middle of a long resident file stop firing —
  they are present but effectively lost.
- Carrying every procedure at all times wastes context on situations
  that are not happening.

So the resident file holds only **a short core plus a map**: a few
principles that apply to every turn, and a table of
*situation → skill*. Everything else lives in skills, selected
just-in-time. When a new rule is learned, it goes into the owning
skill's body — never into the resident file.

## Authoring rules

- **One situation per skill.** If the trigger can't be stated in one
  line ("when X happens", "before doing Y"), it isn't a skill yet.
- **The description is the trigger.** Write it as the matching rule
  an agent (or a search) would use: what situation, what action.
  Vague descriptions mean the skill never fires.
- **Self-contained.** The body carries the full procedure, the
  evidence standard, and the known failure cases — the reader should
  not need the conversation that produced it.
- **Fixes land in the owning skill.** When a failure traces back to a
  procedure, the correction goes into that skill's body in the same
  change, not into a chat note or the resident file.
- **Small and concrete beats general.** Extract the pattern only
  after the concrete version works.

## Multi-surface setups

When the same human is served from several surfaces (an app, a web
chat, a CLI), the skill bodies live **once** in the records repo.
Other surfaces keep *thin pointer skills*: a stub with the same name
and description whose body says "pull the records repo and read
`skills/<name>/SKILL.md` in full". If a surface's copy and the repo
disagree, the repo wins.

An example skill ships in [examples/](examples/).

## Included skills (full set, 2026-11-04)

Generalized from a working agent-VM setup (45 procedures). Operator
names, mailboxes, chat ids, and company references were replaced with
placeholders; record paths point at the records repo, not one operator's
checkout. `SKILL.md only` rows name helper scripts that lived outside
the skill directory on the source system — those helpers are not
shipped; the body documents the procedure. `SKILL.md + helpers` rows
ship the skill's own scripts and references.

| Skill | Shipped | What it is for |
|---|---|---|
| `beeper-messages` | SKILL.md only | Beeper全体の新着・未返信確認と返信案。接続中の全アカウント（WhatsApp・LINE・Messenger・Instagram・Matrix等）を確認し、仕事・友人・デートを勝手に絞らない。WhatsAppと... |
| `brainstorming` | SKILL.md only | You MUST use this before any creative work - creating features, building components, adding functionality, ... |
| `calendar_blocks` | SKILL.md only | Move a calendar event's linked travel blocks with it and verify contiguity afterwards, used whenever you ch... |
| `challenge` | SKILL.md only | 前提を壊す自律思考ループ。/challenge <トピック> or /challenge 3 <トピック> で発動 |
| `records_sot_landing` | SKILL.md only | Mirror real-world facts into records repo and land them through the gates in the same run, used whenever yo... |
| `cron-optimizer` | SKILL.md + helpers | cronジョブの棚卸し・最適化（重複検出・スケジュール集中・不要ジョブ） |
| `cross-check` | SKILL.md only | Codexペインにコードレビューを依頼し、フィードバックを取得する |
| `diagnose_channel_linking` | SKILL.md only | Diagnose a messaging channel that will not link or sync, and route the fix by symptom. |
| `doc-converter` | SKILL.md + helpers | ドキュメント変換（PDF/DOCX/XLSX/HTML → Markdown） |
| `document_interpretation_review` | SKILL.md only | Interpret a contract, financial-product or legal document's operative terms and cross-check with a second a... |
| `docusign-send` | SKILL.md only | DocuSignテンプレートを使ったエンベロープの送信・追跡を自動化する |
| `epub-converter` | SKILL.md + helpers | Convert Markdown documents into professional EPUB3 ebook files. |
| `failure_mechanisms` | SKILL.md only | Record failures in the ledger and close repeats with structural mechanisms that records repo documents, use... |
| `foreman_handoff` | SKILL.md only | Prepare factory-handoff task files and F: instructions that pass the cap floor check and the template check... |
| `grok-search` | SKILL.md + helpers | Real-time search over X/Twitter and the web via the Grok API (x_search + web_search). |
| `imozuru` | SKILL.md + helpers | 知らない分野にキャッチアップするとき、汎用的な言葉から界隈の用語・中心の人・媒体（学会・雑誌・個人ブログ・動画・リポジトリ・一覧）を特定し、 引用・リンク・著者を芋づる式にたどって、目当ての原文（論文も個人の記事や... |
| `journal` | SKILL.md + helpers | 日記、今日の振り返り、日記の続き・保存、月次振り返りを行う。カレンダー・Gmail・GitHubから出来事を復元し、感情辞典で本人が言葉を確かめ、情報量と意味を保った全文をthe records repoへ保存する... |
| `kakugo` | SKILL.md only | プライベートの不確実な決断で、最悪のパターンを複数想定し、覚悟（受け入れる線・受け入れない線）と対応策を決める。the operator's established pattern of assuming the ... |
| `line` | SKILL.md only | LINE未読メッセージを確認・分類し、返信案作成・送信を行う（Matrix Bridge経由） |
| `mail` | SKILL.md only | Gmail未読メールを分類・返信案作成・送信し、後続タスクまで完遂する（3層アーキテクチャ） |
| `messenger` | SKILL.md only | Facebook Messengerの未読メッセージを確認・分類し、返信案作成・送信を行う（Chrome CDP / AppleScript経由） |
| `moltbook-interact` | SKILL.md + helpers | Interact with Moltbook social network for AI agents. Post, reply, browse, and analyze engagement. Use when ... |
| `ocr-parser` | SKILL.md + helpers | 画像/PDFからテキスト抽出（Tesseract OCR、日本語対応） |
| `opencode-delegate` | SKILL.md + helpers | Delegate a coding task, code read, or quick question to opencode running DeepSeek V4.1 Flash (free on OpenC... |
| `pdf` | SKILL.md + helpers | Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting t... |
| `pptx` | SKILL.md + helpers | Use this skill any time a .pptx file is involved in any way — as input, output, or both. This includes: cre... |
| `reply_drafting` | SKILL.md only | Draft replies and messages in the operator's own voice — read the operator's voice examples and the actual ... |
| `research_method` | SKILL.md only | Ground any research or design in best practices copied from practitioners and in listed evidence, used when... |
| `saiaku` | SKILL.md + helpers | あるテーマ（結婚・子育て・移住・留学など、人生の決断）で実際に起きた「最悪のパターン」を、imozuru で web から原文ごと集め、当事者の一人称の原文・頻度の統計・出典つきのパターン一覧（patterns.m... |
| `schedule-optimizer` | SKILL.md + helpers | 日程調整の自動最適化（空き時間マージ・候補生成・バッファ計算） |
| `schedule-reply` | SKILL.md only | 日程調整の返信を作成・送信・後続処理まで一気通貫で実行する |
| `scrapling` | SKILL.md + helpers | Scraplingでウェブサイトをスクレイピングする。web_fetchで取れないJS重いサイトやCloudflare保護サイトに使う。 |
| `session-wrapup` | SKILL.md + helpers | セッション終了時の自動処理（commit検出・memory整理・ルール抽出・次回準備） |
| `slack` | SKILL.md only | Slackメッセージの確認・分類・返信案作成・送信を行う（slack-mcp-server経由） |
| `sride-receipts` | SKILL.md + helpers | S.RIDE領収書をGmailからダウンロードし、決済手段別に分類する |
| `systematic-debugging` | SKILL.md + helpers | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| `team-manage` | SKILL.md only | 5エージェントチームのタスク管理・進捗監視・クロスレビュー・品質管理を行う |
| `test-driven-development` | SKILL.md + helpers | Use when implementing any feature or bugfix, before writing implementation code |
| `today` | SKILL.md only | 朝のブリーフィング — メール・LINE・カレンダーを並列取得し、トリアージ＋返信処理まで完遂する |
| `todo_verification` | SKILL.md only | Settle a todo entry's outcome against Beeper, Google Calendar and Gmail before changing it, used whenever y... |
| `trip_design_brief` | SKILL.md only | Frame itinerary options from the generated window brief after a premise audit, used whenever you design or ... |
| `uber-receipts` | SKILL.md + helpers | Uber領収書を一括ダウンロードし、決済手段別（OPERATOR-COMPANY/PayPay/Cash等）に分類する |
| `whatsapp-messages` | SKILL.md only | WhatsAppと指定された連絡・返信・未返信確認。仕事・友人・デートを含むWhatsApp全体が対象。Beeper全体の依頼はbeeper-messagesへ。実会話に沿って文案を作り、承認済み文面のみ送信・再読... |
| `x-scraper` | SKILL.md + helpers | Use the X/Twitter API v2 directly for tweet search, user lookup, and trend retrieval, with no external SaaS... |
| `xlsx` | SKILL.md + helpers | Use this skill any time a spreadsheet file is the primary input or output. This means any task where the us... |

Notes:

- `imozuru` ships the skill text, the theory reference, and the
  standalone `scripts/*.py` helpers (see `skills/imozuru/README.md`
  for the fetch guard and the `IMOZURU_ALLOW_PRIVATE` operator option).
  Guide-site assets and guide-screenshot generators are omitted.
- `epub-converter` ships the converter (`markdown-to-epub/`) only;
  release infra, changelogs, and test outputs are omitted.
- `moltbook-interact` omits the install registry metadata
  (`.skillhub/`); `uber-receipts` omits its `logs/` directory.
- `receipt_lib` is not a skill; it ships as `tools/receipt-lib/`
  (company-card receipt classification, used by the receipt skills).
