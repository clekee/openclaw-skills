#!/usr/bin/env bash
# openclaw-watchdog.sh — Monitor OpenClaw gateway health via launchd.
# If the gateway crashes repeatedly (>= CRASH_THRESHOLD times in WINDOW seconds),
# invoke Claude Code to diagnose and fix the config, then restart.
#
# Designed to run as a periodic LaunchAgent (e.g. every 60s).

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────
LABEL="ai.openclaw.gateway"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
CONFIG_PATH="${HOME}/.openclaw/openclaw.json"
LOG_DIR="${HOME}/.openclaw/logs"
LOG_FILE="${LOG_DIR}/gateway.err.log"
STDOUT_LOG="${LOG_DIR}/gateway.log"
WATCHDOG_STATE="${LOG_DIR}/watchdog-state.json"
WATCHDOG_LOG="${LOG_DIR}/watchdog.log"

CRASH_THRESHOLD="${OPENCLAW_WATCHDOG_CRASH_THRESHOLD:-5}"  # crashes in window
WINDOW_SECS="${OPENCLAW_WATCHDOG_WINDOW_SECS:-120}"         # time window
MAX_FIX_ATTEMPTS="${OPENCLAW_WATCHDOG_MAX_FIX:-2}"
CLAUDE_TIMEOUT="${OPENCLAW_WATCHDOG_CLAUDE_TIMEOUT:-300}"
COOLDOWN_SECS="${OPENCLAW_WATCHDOG_COOLDOWN_SECS:-600}"     # min seconds between fix runs

# Optional Telegram notification
TELEGRAM_TARGET="${OPENCLAW_FIX_TELEGRAM_TARGET:-}"

# ── Helpers ─────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$WATCHDOG_LOG"; }

notify() {
  local msg="$1"
  [[ -z "$TELEGRAM_TARGET" ]] && return 0
  /opt/homebrew/bin/openclaw message send \
    --channel telegram --target "$TELEGRAM_TARGET" --message "$msg" 2>/dev/null || true
}

find_claude() {
  for c in "$HOME/.local/bin/claude" /opt/homebrew/bin/claude /usr/local/bin/claude; do
    [[ -x "$c" ]] && { echo "$c"; return 0; }
  done
  command -v claude 2>/dev/null || echo ""
}

is_gateway_running() {
  # Check if launchd thinks it's running AND process responds
  local pid
  pid=$(launchctl list "$LABEL" 2>/dev/null | awk '/PID/{print $NF}' || true)
  if [[ -z "$pid" || "$pid" == "-" ]]; then
    # Try alternate: parse launchctl list output (tab-separated: PID Status Label)
    pid=$(launchctl list 2>/dev/null | awk -v l="$LABEL" '$3==l {print $1}')
  fi
  [[ -n "$pid" && "$pid" != "-" && "$pid" != "0" ]]
}

get_crash_count() {
  # Count how many times the gateway exited in the recent WINDOW_SECS
  # by looking at launchd's last exit status and error log timestamps
  local now cutoff count=0
  now=$(date +%s)
  cutoff=$((now - WINDOW_SECS))

  # Parse error log for crash signatures (OOM, SIGKILL, uncaught, EADDRINUSE, etc.)
  if [[ -f "$LOG_FILE" ]]; then
    while IFS= read -r line; do
      # Try to extract timestamp from log lines (ISO or common formats)
      local ts
      ts=$(echo "$line" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}' | head -1)
      if [[ -n "$ts" ]]; then
        local epoch
        epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${ts/T/T}" +%s 2>/dev/null || \
                date -j -f "%Y-%m-%d %H:%M:%S" "$ts" +%s 2>/dev/null || echo 0)
        if [[ "$epoch" -ge "$cutoff" ]]; then
          count=$((count + 1))
        fi
      fi
    done < <(grep -iE "fatal|SIGKILL|SIGABRT|uncaught|EADDRINUSE|segfault|OOM|panic" "$LOG_FILE" 2>/dev/null | tail -20)
  fi

  # Also check: is it currently NOT running despite KeepAlive=true? That's a crash signal.
  if ! is_gateway_running; then
    count=$((count + 1))
  fi

  echo "$count"
}

check_cooldown() {
  if [[ -f "$WATCHDOG_STATE" ]]; then
    local last_fix now
    last_fix=$(python3 -c "import json; print(json.load(open('$WATCHDOG_STATE')).get('last_fix_epoch', 0))" 2>/dev/null || echo 0)
    now=$(date +%s)
    if [[ $((now - last_fix)) -lt "$COOLDOWN_SECS" ]]; then
      return 1  # still in cooldown
    fi
  fi
  return 0
}

save_state() {
  local status="$1" message="$2"
  python3 -c "
import json
state = {'last_fix_epoch': $(date +%s), 'status': '$status', 'message': '''$message''', 'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'}
json.dump(state, open('$WATCHDOG_STATE', 'w'), indent=2)
"
}

collect_errors() {
  echo "=== Gateway stderr (last 60 lines) ==="
  tail -60 "$LOG_FILE" 2>/dev/null || echo "(no stderr log)"
  echo ""
  echo "=== Gateway stdout (last 30 lines) ==="
  tail -30 "$STDOUT_LOG" 2>/dev/null || echo "(no stdout log)"
  echo ""
  echo "=== Config validation ==="
  if [[ -f "$CONFIG_PATH" ]]; then
    python3 -m json.tool "$CONFIG_PATH" >/dev/null 2>&1 && echo "JSON valid" || echo "JSON INVALID"
  else
    echo "Config file missing: $CONFIG_PATH"
  fi
}

restart_gateway() {
  log "Restarting gateway via launchctl..."
  launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || \
  launchctl stop "$LABEL" 2>/dev/null
  sleep 2
  launchctl start "$LABEL" 2>/dev/null || true
  sleep 6
  is_gateway_running
}

# ── Main ────────────────────────────────────────────────────────────────
log "Watchdog check started"

# If gateway is healthy, nothing to do
if is_gateway_running; then
  # Quick health check via HTTP
  HTTP_OK=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${GATEWAY_PORT}/health" 2>/dev/null || echo "000")
  if [[ "$HTTP_OK" == "200" || "$HTTP_OK" == "204" ]]; then
    log "Gateway healthy (HTTP $HTTP_OK). Nothing to do."
    exit 0
  fi
  log "Gateway process running but HTTP check failed ($HTTP_OK). Continuing..."
fi

# Gateway is down or unhealthy
CRASHES=$(get_crash_count)
log "Crash signals in last ${WINDOW_SECS}s: $CRASHES (threshold: $CRASH_THRESHOLD)"

if [[ "$CRASHES" -lt "$CRASH_THRESHOLD" ]]; then
  # Not enough crashes yet — let launchd KeepAlive handle it
  log "Below threshold. Letting launchd handle restart."
  exit 0
fi

# Check cooldown
if ! check_cooldown; then
  log "In cooldown period. Skipping auto-fix."
  exit 0
fi

log "⚠️ Crash threshold reached. Starting auto-fix..."
notify "🔧 OpenClaw gateway 反复崩溃 ($CRASHES 次/${WINDOW_SECS}s)，启动 Claude Code 自动修复..."

CLAUDE_CODE="$(find_claude)"
if [[ -z "$CLAUDE_CODE" ]]; then
  log "❌ Claude Code not found. Cannot auto-fix."
  notify "🔴 Gateway 反复崩溃但 Claude Code 未安装，无法自动修复。"
  save_state "no-claude" "Claude Code not found"
  exit 1
fi

ERROR_CONTEXT="$(collect_errors)"

for attempt in $(seq 1 "$MAX_FIX_ATTEMPTS"); do
  log "Fix attempt $attempt/$MAX_FIX_ATTEMPTS"

  FIX_PROMPT="OpenClaw Gateway on macOS keeps crashing and restarting. Fix the issue.

LaunchAgent: $LABEL
Config: $CONFIG_PATH
Gateway port: $GATEWAY_PORT
Logs: $LOG_DIR

Error context:
$ERROR_CONTEXT

Rules:
- Prefer minimal changes to config.
- Do NOT remove known-good baseline plugins unless clearly broken.
- After changes, verify JSON: python3 -m json.tool $CONFIG_PATH > /dev/null
- Do NOT restart the service yourself — the watchdog handles that.
- Show what you changed."

  fix_output=$(timeout "$CLAUDE_TIMEOUT" "$CLAUDE_CODE" -p "$FIX_PROMPT" \
    --allowedTools "Read,Write,Edit,Bash" \
    --max-turns 10 \
    2>&1 || echo "Claude Code failed or timed out")

  log "Claude output (tail 20):"
  echo "$fix_output" | tail -20 >> "$WATCHDOG_LOG"

  # Validate config before restart
  if [[ -f "$CONFIG_PATH" ]]; then
    if ! python3 -m json.tool "$CONFIG_PATH" >/dev/null 2>&1; then
      log "❌ Fix produced invalid JSON. Skipping restart."
      notify "🔴 自动修复第 $attempt 次产生了无效 JSON，跳过重启。"
      ERROR_CONTEXT="$(collect_errors)"
      continue
    fi
  fi

  if restart_gateway; then
    log "✅ Gateway restarted successfully after fix attempt $attempt"
    notify "✅ Gateway 自动修复成功 (第 $attempt 次尝试)。"
    save_state "ok" "Fixed on attempt $attempt"
    exit 0
  fi

  ERROR_CONTEXT="$(collect_errors)"
done

log "❌ Auto-fix failed after $MAX_FIX_ATTEMPTS attempts."
notify "🔴 Gateway 自动修复失败 ($MAX_FIX_ATTEMPTS 次尝试均失败)，需要手动干预。"
save_state "failed" "Failed after $MAX_FIX_ATTEMPTS attempts"
exit 1
