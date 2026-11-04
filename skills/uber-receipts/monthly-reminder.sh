#!/bin/bash
# monthly-reminder.sh - 月末にUber領収書ダウンロードをリマインド
#
# launchdで毎月28日に実行される想定
# Discordに通知を送り、承認を待つ

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/reminder.log"
DISCORD_CHANNEL="channel:1465129618645192707"  # Recordsbot通知チャンネル

mkdir -p "$SCRIPT_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 現在の年月を取得
YEAR=$(date '+%Y')
MONTH=$(date '+%-m')

log "=== Uber Receipts Monthly Reminder ==="
log "Target month: $YEAR/$MONTH"

# Discordに通知を送信
MESSAGE="📋 **Uber領収書ダウンロード**

今月分（${YEAR}/${MONTH}）のUber領収書をダウンロードしますか？

\`\`\`
~/records/skills/uber-receipts/run.sh
\`\`\`

Chrome起動 → ログイン待ち → ダウンロード まで自動で進みます。"

# recordsbotで送信
if command -v recordsbot &> /dev/null; then
    log "Sending Discord notification..."
    recordsbot message send --channel discord --target "$DISCORD_CHANNEL" --message "$MESSAGE" 2>&1 | tee -a "$LOG_FILE"
    log "Notification sent"
else
    log "WARNING: recordsbot not found, falling back to echo"
    echo "$MESSAGE"
fi

log "=== Reminder Complete ==="
