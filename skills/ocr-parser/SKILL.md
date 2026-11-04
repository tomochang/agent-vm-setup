---
name: ocr-parser
description: 画像/PDFからテキスト抽出（Tesseract OCR、日本語対応）
---

# ocr-parser スキル

画像（JPG/PNG/TIFF等）またはPDFからテキストを抽出します。
日本語・英語の混在文書に対応。バッチ処理・JSON出力も可能。

## コマンド

```
/ocr <file>          — ファイルまたはディレクトリのOCR
/ocr-parse <file>    — 同上
```

## セットアップ

```bash
# 依存パッケージをインストール（要sudo）
sudo bash skills/ocr-parser/scripts/install.sh
```

インストールされるもの:
- `tesseract-ocr` — OCRエンジン本体
- `tesseract-ocr-jpn` — 日本語言語パック
- `tesseract-ocr-eng` — 英語言語パック
- `poppler-utils` — PDF→画像変換
- Python: `pytesseract`, `Pillow`, `pdf2image`, `pytest`

## CLI使用例

```bash
# 画像1枚（英語）
python3 skills/ocr-parser/scripts/ocr.py image.png --lang eng

# PDF（日本語+英語）
python3 skills/ocr-parser/scripts/ocr.py document.pdf --lang jpn+eng

# JSON出力
python3 skills/ocr-parser/scripts/ocr.py report.png --json

# ファイルに保存
python3 skills/ocr-parser/scripts/ocr.py report.pdf --json --output result.json

# ディレクトリ内を一括処理
python3 skills/ocr-parser/scripts/ocr.py ./scans/ --lang jpn+eng --json --output batch.json
```

## オプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--lang`  | `jpn+eng` | tesseract 言語コード |
| `--json`  | off       | JSON形式で出力 |
| `--output`| stdout    | 出力先ファイルパス |

## 出力形式

### プレーンテキスト（デフォルト）
```
=== image.png ===
Hello World
抽出されたテキスト...
```

### JSON
```json
[
  {
    "file": "image.png",
    "text": "Hello World\n..."
  },
  {
    "file": "document.pdf",
    "pages": [
      {"page": 1, "text": "ページ1のテキスト..."},
      {"page": 2, "text": "ページ2のテキスト..."}
    ]
  }
]
```

## サポート形式

| 形式 | 拡張子 |
|------|--------|
| 画像 | `.jpg` `.jpeg` `.png` `.tiff` `.tif` `.bmp` `.gif` `.webp` |
| PDF  | `.pdf` |

## テスト実行

```bash
cd skills/ocr-parser
python3 -m pytest scripts/test_ocr.py -v
```

## ファイル構成

```
skills/ocr-parser/
├── SKILL.md          — このファイル
└── scripts/
    ├── ocr.py        — メインスクリプト（CLI + APIとして使用可）
    ├── test_ocr.py   — pytestテスト（TDDで作成）
    └── install.sh    — 依存パッケージインストールスクリプト
```

## Pythonモジュールとして使う

```python
from scripts.ocr import extract_text_from_image, extract_text_from_pdf, process_path

# 画像からテキスト抽出
text = extract_text_from_image("scan.png", lang="jpn+eng")

# PDFからテキスト抽出（ページ別リスト）
pages = extract_text_from_pdf("doc.pdf", lang="jpn")
for p in pages:
    print(f"Page {p['page']}: {p['text']}")

# バッチ処理
results = process_path("./scans/", lang="jpn+eng", output_json=True, output_path="out.json")
```
