#!/usr/bin/env bash
# X/Twitter API スクレイパースキル 依存インストール
set -euo pipefail

echo "=== x-scraper: 依存パッケージのインストール ==="

# requests のみ必要
pip install --quiet requests

echo "✅ インストール完了"
echo ""
echo "次のステップ:"
echo "  1. X Developer Portal でBearer Tokenを取得:"
echo "     https://developer.twitter.com/en/portal/dashboard"
echo "  2. 環境変数を設定:"
echo "     export X_BEARER_TOKEN='your_bearer_token_here'"
echo "  3. 動作確認:"
echo "     python3 scripts/x_client.py search 'Python' --max 10"
