#!/usr/bin/env bash
# Run one non-interactive opencode task (default: DeepSeek V4.1 Flash Free via OpenCode Zen).
# usage: oc-run.sh [--dir DIR] [--plan] [--model PROVIDER/MODEL] [--timeout SEC] "prompt"
set -u
MODEL="opencode/deepseek-v4.1-flash-free"; DIR="$PWD"; AGENT=""; TIMEOUT=300; PROMPT=""
usage() { sed -n '3p' "$0" | sed 's/^# //' >&2; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --plan) AGENT="plan"; shift ;;
    --model) MODEL="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) PROMPT="$1"; shift ;;
  esac
done
[ -n "$PROMPT" ] || usage
DIR="$(cd "$DIR" 2>/dev/null && pwd -P)" || { echo "oc-run: no such dir" >&2; exit 2; }

# The provider sees every file opencode reads: never run on the private repo or the whole home dir.
RECORDS="$(cd "$HOME/records" 2>/dev/null && pwd -P || echo "$HOME/records")"
HOMEP="$(cd "$HOME" && pwd -P)"
case "$DIR/" in "$RECORDS"/*) echo "oc-run: refusing to run inside $RECORDS (private data)" >&2; exit 2 ;; esac
[ "$DIR" = "$HOMEP" ] && { echo "oc-run: refusing to run in \$HOME; cd into a project dir" >&2; exit 2; }

args=(run --dir "$DIR" -m "$MODEL")
[ -n "$AGENT" ] && args+=(--agent "$AGENT")
args+=("$PROMPT")

# stdin closed: an open stdin can leave `opencode run` waiting. perl alarm = portable timeout on macOS.
perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" opencode "${args[@]}" </dev/null 2>&1 \
  | sed $'s/\033\\[[0-9;]*[A-Za-z]//g'
rc=${PIPESTATUS[0]}
[ "$rc" -eq 142 ] && { echo "oc-run: timed out after ${TIMEOUT}s" >&2; exit 124; }
exit "$rc"
