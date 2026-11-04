#!/bin/bash
# run.sh - S.RIDE領収書ダウンロードをワンコマンドで実行
#
# Usage:
#   ./run.sh                                # 今月分
#   ./run.sh 2026/1                         # 指定月
#   ./run.sh 2026/1 --statement ~/company-card.csv  # COMPANY_CARD突合あり

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 引数処理
if [[ -n "$1" && "$1" != --* ]]; then
    MONTH="$1"
    shift
else
    YEAR=$(date '+%Y')
    MONTH_NUM=$(date '+%-m')
    MONTH="$YEAR/$MONTH_NUM"
fi

EXTRA_ARGS="$@"

echo "========================================"
echo "S.RIDE領収書ダウンロード"
echo "========================================"
echo "対象月: $MONTH"
echo ""

uv run "$SCRIPT_DIR/download.py" --month "$MONTH" $EXTRA_ARGS

echo ""
echo "========================================"
echo "完了！"
echo "========================================"
