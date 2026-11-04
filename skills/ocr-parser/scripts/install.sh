#!/bin/bash
# install.sh — OCR parser依存パッケージのインストール
set -e

echo "=== OCR Parser: 依存パッケージのインストール ==="

# システムパッケージ
echo "[1/3] tesseract-ocr + 言語パック + poppler-utils のインストール..."
apt-get update -qq
apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-eng \
    poppler-utils \
    python3-pip

echo "[2/3] Python依存パッケージのインストール..."
pip3 install --user --quiet pytesseract Pillow pdf2image pytest

echo "[3/3] インストール確認..."
tesseract --version
python3 -c "import pytesseract, PIL, pdf2image; print('Python packages OK')"

echo ""
echo "✅ インストール完了！"
echo "使い方: python3 scripts/ocr.py <file_or_dir> [--lang jpn+eng] [--json] [--output /path]"
