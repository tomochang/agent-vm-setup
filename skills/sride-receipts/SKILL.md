---
name: sride-receipts
description: S.RIDE領収書をGmailからダウンロードし、決済手段別に分類する
---

# S.RIDE領収書ダウンロード＆決済手段別分類

## 概要

S.RIDEタクシーの領収書PDFをGmailから一括ダウンロードし、決済手段別に分類・集計する。
経理処理（特にOPERATOR-COMPANY法人カードの経費精算）に使用。

## 使用方法

```bash
# 今月分
the records checkout/skills/sride-receipts/run.sh

# 特定月
the records checkout/skills/sride-receipts/run.sh 2026/1

# OPERATOR-COMPANY明細と突合して分類
the records checkout/skills/sride-receipts/run.sh 2026/1 --statement ~/path/to/company-statement.csv
```

### 手動実行

```bash
# 直近の領収書メール
uv run the records checkout/skills/sride-receipts/download.py --month 2026/1

# OPERATOR-COMPANY明細による突合分類
uv run the records checkout/skills/sride-receipts/download.py --month 2026/1 --statement ~/company-statement.csv

# 出力先指定
uv run the records checkout/skills/sride-receipts/download.py --month 2026/1 -o the records checkout/receipts
```

## 前提条件

- **gog** CLI がインストール済み (`brew install gog` / go install)
- Gmail API の認証設定済み
- S.RIDE領収書メールが `noreply-invoice@cs.sride.co.jp` から届いている

## 処理フロー

1. `gog gmail search` で S.RIDE領収書メールを検索
2. `gog gmail get` でメール詳細を取得（添付ファイル一覧）
3. `gog gmail attachment` で各PDFをダウンロード
4. ファイル名からメタデータを抽出（日付・金額・タクシー会社）
5. 分類:
   - OPERATOR-COMPANY明細がある場合: 日付±1日 + 金額完全一致で突合
   - 明細がない場合: `CreditCard` として分類
6. `the records checkout/receipts/{company|other}/YYYYMM/sride/` に配置
7. summary.md と results.json を生成

## 出力

### ディレクトリ構造

```
the records checkout/receipts/
├── company/
│   └── 202601/
│       └── sride/
│           └── 20260101_1404_receipt_JPY3800_T2011801002719_taxifare.pdf
└── other/
    └── 202601/
        └── sride/
            └── 20260115_0125_receipt_JPY2700_T2011801002719_taxifare.pdf
```

### ファイル命名規則

S.RIDEメールの添付ファイル名をそのまま使用:
`YYYYMMDD_HHMM_receipt_JPY{金額}_T{事業者番号}_taxifare.pdf`

## 決済手段の判定

S.RIDEの領収書PDFには「クレジットカード利用」としか記載されず、カードブランド名は表示されない。

| モード      | 条件                    | 結果       |
| ----------- | ----------------------- | ---------- |
| OPERATOR-COMPANY突合 | 日付±1日 & 金額完全一致 | OPERATOR-COMPANY    |
| OPERATOR-COMPANY突合 | マッチなし              | CreditCard |
| 明細なし    | -                       | CreditCard |

## 経理処理との連携

### OPERATOR-COMPANY請求書転送

OPERATOR-COMPANYで決済した領収書は、以下のメールアドレスに転送することで紐付け:

```
00000000-0000-0000-0000-000000000000@mail.example.com
```
