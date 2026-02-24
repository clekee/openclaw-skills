#!/usr/bin/env bash
# safe-gateway-restart.sh (macOS) — Restart OpenClaw gateway with optional Claude Code auto-fix.
# Usage: ./safe-gateway-restart.sh [reason]

set -euo pipefail

REASON="${1:-manual restart}"
MAX_RETRIES="${SAFE_RESTART_MAX_RETRIES:-2}"
LABEL="ai.openclaw.gateway"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
CONFIG_PATH="${HOME}/.openclaw/openclaw.json"
LOG_DIR="${HOME}/.openclaw/logs"
LOG_FILE="${LOG_DIR}/gateway.err.log"
TELEGRAM_TARGET="${SAFE_RESTART_TELEGRAM_TARGET:-}"

find_claude() {
  for c in "$HOME/.local/bin/claude" /opt/homebrew/bin/claude /usr/local/bin/claude; do
    [[ -x "$c" ]] && { echo "$c"; return 0; }
  done
  command -v claude 2>/dev/null || echo ""
}

notify() {
  local msg="$1"
  [[ -z "$TELEGRAM_TARGET" ]] && return 0
  /opt/homebrew/bin/openclaw message send \
    --channel telegram --target "$TELEGRAM_TARGET" --message "$msg" 2>/dev/null || true
}

check_gateway_errors() {
  local errors=""
  if [[ -f "$LOG_FILE" ]]; then
    errors=$(tail -60 "$LOG_FILE" | grep -i "invalid config\|Config validation failed\|plugin.*not found\|ERROR.*plugin" | tail -10 || true)
  fi
  local status_output
  status_output=$(/opt/homebrew/bin/openclaw gateway status 2>&1 || true)
  if echo "$status_output" | grep -qi "invalid config\|Config invalid"; then
    errors="$errors
$status_output"
  fi
  echo "$errors"
}

do_restart() {
  echo "[$(date '+%H:%M:%S')] Restarting gateway (reason: $REASON)…"
  launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || {
    launchctl stop "$LABEL" 2>/dev/null || true
    sleep 1
    launchctl start "$LABEL" 2>/dev/null || true
  }
  echo "[$(date '+%H:%M:%S')] Waiting 6s for gateway to stabilize…"
  sleep 6
}

CLAUDE_CODE="$(find_claude)"
CLAUDE_TIMEOUT="${SAFE_RESTART_CLAUDE_TIMEOUT_SECS:-300}"

echo "=== Safe Gateway Restart (macOS) ==="
echo "LaunchAgent: $LABEL"
echo "Reason: $REASON"
echo "Claude: ${CLAUDE_CODE:-NOT FOUND}"
echo

for attempt in $(seq 1 $((MAX_RETRIES + 1))); do
  echo "--- Attempt $attempt ---"
  do_restart
  errors="$(check_gateway_errors)"

  if [[ -z "$errors" || "$errors" =~ ^[[:space:]]*$ ]]; then
    echo "[$(date '+%H:%M:%S')] ✅ Gateway restarted successfully (attempt $attempt)"
    exit 0
  fi

  echo "[$(date '+%H:%M:%S')] ❌ Errors detected:"
  echo "$errors"

  if [[ $attempt -gt $MAX_RETRIES ]]; then
    notify "🔴 Gateway restart failed after $MAX_RETRIES fix attempts."
    exit 1
  fi

  if [[ -z "$CLAUDE_CODE" ]]; then
    notify "🔴 Gateway restart failed and Claude Code not available."
    exit 1
  fi

  FIX_PROMPT="OpenClaw gateway restart failed with these errors:

$errors

Fix the issue. Common causes:
- Invalid JSON in ~/.openclaw/openclaw.json
- Broken plugin references

Rules:
- Prefer minimal changes.
- After fixing, verify JSON: python3 -m json.tool $CONFIG_PATH > /dev/null
- Do NOT restart the service.
Show what you changed."

  timeout "$CLAUDE_TIMEOUT" "$CLAUDE_CODE" -p "$FIX_PROMPT" \
    --allowedTools "Read,Write,Edit,Bash" \
    --max-turns 10 2>&1 | tail -40

  echo
done
