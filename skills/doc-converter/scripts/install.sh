#!/usr/bin/env bash
# install.sh — Install dependencies for doc-converter skill
set -euo pipefail

echo "=== doc-converter: Installing dependencies ==="

# ---- poppler-utils (pdftotext) ----
if ! command -v pdftotext &>/dev/null; then
    echo "[apt] Installing poppler-utils..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y poppler-utils
    elif command -v brew &>/dev/null; then
        brew install poppler
    else
        echo "WARNING: Cannot install poppler-utils automatically. Install it manually."
    fi
else
    echo "[ok] pdftotext already available"
fi

# ---- python-docx ----
if python3 -c "import docx" 2>/dev/null; then
    echo "[ok] python-docx already installed"
else
    echo "[pip] Installing python-docx..."
    pip3 install --user --quiet python-docx
fi

# ---- openpyxl ----
if python3 -c "import openpyxl" 2>/dev/null; then
    echo "[ok] openpyxl already installed"
else
    echo "[pip] Installing openpyxl..."
    pip3 install --user --quiet openpyxl
fi

# ---- pandoc (optional fallback for DOCX) ----
if command -v pandoc &>/dev/null; then
    echo "[ok] pandoc already available"
else
    echo "[info] pandoc not found (optional). Install with: sudo apt-get install pandoc"
fi

echo ""
echo "=== Installation complete ==="
echo "Run: python3 scripts/convert.py <file> [--output out.md]"
