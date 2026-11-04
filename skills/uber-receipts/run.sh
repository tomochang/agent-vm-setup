#!/bin/bash
# run.sh - Uber領収書ダウンロードをワンコマンドで実行
#
# Usage:
#   ./run.sh                    # 今月分
#   ./run.sh 2026/1             # 指定月
#   ./run.sh --days 30          # 直近30日

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CDP_PORT=9222
CDP_URL="http://localhost:$CDP_PORT"

# 引数処理
if [[ -n "$1" && "$1" != --* ]]; then
    # 月指定 (2026/1 形式)
    DOWNLOAD_ARGS="--month $1"
elif [[ -n "$1" ]]; then
    # オプション指定 (--days 30 等)
    DOWNLOAD_ARGS="$@"
else
    # デフォルト: 今月
    YEAR=$(date '+%Y')
    MONTH=$(date '+%-m')
    DOWNLOAD_ARGS="--month $YEAR/$MONTH"
fi

echo "========================================"
echo "Uber領収書ダウンロード"
echo "========================================"
echo "対象: $DOWNLOAD_ARGS"
echo ""

# 1. 既存Chromeを終了してリモートデバッグモードで再起動
echo "[1/4] Chromeを再起動中..."
pkill "Google Chrome" 2>/dev/null || true
sleep 2

"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=$CDP_PORT \
    --user-data-dir=/tmp/chrome-uber-debug \
    "https://riders.uber.com/trips" \
    > /dev/null 2>&1 &

# 2. CDP接続を待機
echo "[2/4] Chrome起動を待機中..."
for i in {1..30}; do
    if curl -s "$CDP_URL/json/version" > /dev/null 2>&1; then
        echo "       Chrome準備完了"
        break
    fi
    sleep 1
done

if ! curl -s "$CDP_URL/json/version" > /dev/null 2>&1; then
    echo "ERROR: Chromeに接続できません"
    exit 1
fi

# 3. ログイン待ち
echo ""
echo "[3/4] Uberにログインしてください"
echo "       ログインが完了したらEnterを押してください..."
echo ""
read -p "       > "

# 4. ダウンロード実行
echo ""
echo "[4/4] 領収書をダウンロード中..."
echo ""

cd "$SCRIPT_DIR"
uv run download.py $DOWNLOAD_ARGS -o "$SCRIPT_DIR/output"

echo ""
echo "========================================"
echo "完了！"
echo "出力: $SCRIPT_DIR/output/"
echo "========================================"
