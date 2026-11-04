---
name: uber-receipts
description: Uber領収書を一括ダウンロードし、決済手段別（OPERATOR-COMPANY/PayPay/Cash等）に分類する
---

# Uber領収書ダウンロード＆決済手段別分類

## 概要

Uber (riders.uber.com) から領収書PDFを一括ダウンロードし、決済手段別に分類・集計する。
経理処理（特にOPERATOR-COMPANY法人カードの経費精算）に使用。

## 使用方法

### ワンコマンド実行（推奨）

```bash
# 今月分
the records checkout/skills/uber-receipts/run.sh

# 特定月
the records checkout/skills/uber-receipts/run.sh 2026/1

# 直近30日分
the records checkout/skills/uber-receipts/run.sh --days 30
```

Chrome起動 → Uberページを開く → ログイン待ち → ダウンロード まで自動で進む。

### 手動実行（Chrome起動済みの場合）

```bash
# 直近30日分
uv run the records checkout/skills/uber-receipts/download.py --days 30

# 特定月（2026年1月）
uv run the records checkout/skills/uber-receipts/download.py --month 2026/1

# 日付範囲指定
uv run the records checkout/skills/uber-receipts/download.py --start 2026-01-01 --end 2026-01-31

# 全件
uv run the records checkout/skills/uber-receipts/download.py --all
```

## 前提条件

- **uv がインストール済み** (Homebrew: `brew install uv`)
- ワンコマンド実行の場合、Chromeは自動で起動される

## 出力

### ファイル

指定した出力ディレクトリに以下が生成される:

```
receipts/
├── 2026-01-05_1200JPY_OPERATOR-COMPANY_abc12345.pdf
├── 2026-01-10_800JPY_PayPay_def67890.pdf
├── 2026-01-15_1500JPY_Cash_ghi11111.pdf
├── summary.md      # 決済手段別サマリー
└── results.json    # 全結果のJSON
```

### ファイル命名規則

`YYYY-MM-DD_金額JPY_決済手段_tripID.pdf`

### サマリー例

```markdown
# Uber領収書 分類結果

## OPERATOR-COMPANY

| 日付       | 金額   | ファイル                                |
| ---------- | ------ | --------------------------------------- |
| 2026-01-05 | ¥1,200 | 2026-01-05_1200JPY_OPERATOR-COMPANY_abc12345.pdf |
| 2026-01-20 | ¥2,500 | 2026-01-20_2500JPY_OPERATOR-COMPANY_xyz99999.pdf |

**小計: 2件**

## PayPay

| 日付       | 金額 | ファイル                              |
| ---------- | ---- | ------------------------------------- |
| 2026-01-10 | ¥800 | 2026-01-10_800JPY_PayPay_def67890.pdf |

**小計: 1件**

## 合計

- OPERATOR-COMPANY: 2件
- PayPay: 1件
- **総合計: 3件**
```

## 決済手段の判定ルール

| 決済手段   | 判定キーワード         |
| ---------- | ---------------------- |
| OPERATOR-COMPANY    | company        |
| PayPay     | paypay                 |
| Cash       | cash, 現金             |
| AMEX       | amex, american express |
| VISA       | visa                   |
| Mastercard | mastercard             |
| その他     | 上記に該当しない場合   |

## 経理処理との連携

### OPERATOR-COMPANY請求書転送

OPERATOR-COMPANYで決済した領収書は、以下のメールアドレスに転送することでカード決済に自動紐付けできる:

```
94b43e74-b63c-4218-8384-55bde30d3b81_xwkuu@mail.operator-company.example
```

### 推奨ワークフロー

1. 月末に `--month` オプションで当月分をダウンロード
2. `summary.md` でOPERATOR-COMPANY分を確認
3. OPERATOR-COMPANY分のPDFをまとめて転送メールに添付

## 月末自動リマインダー

毎月28日 10:00にDiscordで通知が届く。

- **plist:** `~/Library/LaunchAgents/com.records repo.uber-receipts-reminder.plist`
- **スクリプト:** `the records checkout/skills/uber-receipts/monthly-reminder.sh`
- **ログ:** `the records checkout/skills/uber-receipts/logs/`

### 手動で通知をテスト

```bash
the records checkout/skills/uber-receipts/monthly-reminder.sh
```

### launchd操作

```bash
# 状態確認
launchctl list | grep uber-receipts

# 停止
launchctl unload ~/Library/LaunchAgents/com.records repo.uber-receipts-reminder.plist

# 開始
launchctl load ~/Library/LaunchAgents/com.records repo.uber-receipts-reminder.plist
```

## トラブルシューティング

### ブラウザに接続できない

```
Error: Could not connect to browser at http://localhost:9222
```

→ Chromeが `--remote-debugging-port=9222` で起動しているか確認

### 領収書ボタンが見つからない

→ Uberのサイト構造が変更された可能性。スクリーンショットを確認して報告

### ログインが必要と表示される

→ 起動したChromeで手動でUberにログインしてから再実行

## 参考

- [Automating Uber business receipt downloads](https://til.danny.spesh.com/tils/uber-receipt-downloader) — 本実装のベース
- [dmahlow/uber-receipt-downloader](https://github.com/dmahlow/uber-receipt-downloader) — GraphQL API版の参考実装
