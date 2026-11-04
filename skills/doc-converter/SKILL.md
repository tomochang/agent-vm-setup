---
name: doc-converter
description: ドキュメント変換（PDF/DOCX/XLSX/HTML → Markdown）
---

# doc-converter

ドキュメント変換パイプライン。PDF / DOCX / XLSX / HTML を Markdown（またはプレーンテキスト）に変換します。

## 対応フォーマット

| 入力 | 変換エンジン | 依存 |
|------|-------------|------|
| PDF  | pdftotext (poppler-utils) | apt: poppler-utils |
| DOCX / DOC | python-docx → pandoc fallback | pip: python-docx |
| XLSX / XLS | openpyxl | pip: openpyxl |
| HTML / HTM | 組み込みパーサー (stdlib) | 不要 |

## セットアップ

```bash
bash skills/doc-converter/scripts/install.sh
```

## 使い方

```bash
# stdout に出力
python3 skills/doc-converter/scripts/convert.py document.pdf

# ファイルに書き出し
python3 skills/doc-converter/scripts/convert.py report.xlsx --output report.md

# プレーンテキスト形式
python3 skills/doc-converter/scripts/convert.py page.html --format text

# 短縮オプション
python3 skills/doc-converter/scripts/convert.py input.docx -o out.md -f markdown
```

## テスト実行

```bash
cd skills/doc-converter
python3 -m pytest scripts/test_convert.py -v
```

37テスト、依存なしでもモックで全パス。

## エラー対応

| エラー | 意味 | 対処 |
|--------|------|------|
| `UnsupportedFormatError` | 非対応拡張子 | 対応フォーマット表を確認 |
| `DependencyError: pdftotext` | poppler-utils未インストール | `install.sh` を実行 |
| `DependencyError: python-docx / pandoc` | DOCX変換ライブラリ不在 | `install.sh` を実行 |
| `DependencyError: openpyxl` | openpyxl未インストール | `install.sh` を実行 |
| `ConversionError` | 変換処理の失敗 | 入力ファイルの破損を確認 |

## ファイル構成

```
skills/doc-converter/
├── SKILL.md              # このファイル
├── scripts/
│   ├── convert.py        # メインスクリプト（全変換ロジック）
│   ├── test_convert.py   # pytestテスト（37ケース）
│   └── install.sh        # 依存インストールスクリプト
```
