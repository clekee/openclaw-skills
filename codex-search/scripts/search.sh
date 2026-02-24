#!/usr/bin/env bash
# codex-search — Deep web search via Codex CLI with dispatch pattern (background + Telegram callback)
set -euo pipefail

# === Paths (macOS / clekee's Mac mini) ===
RESULT_DIR="/tmp/codex-search-results"
OPENCLAW_BIN="/opt/homebrew/bin/openclaw"
CODEX_BIN="${CODEX_BIN:-/opt/homebrew/bin/codex}"
OPENCLAW_CONFIG="${HOME}/.openclaw/openclaw.json"

# Defaults
PROMPT=""
OUTPUT=""
MODEL="gpt-5.3-codex"
SANDBOX="full-auto"
TIMEOUT=120
TELEGRAM_GROUP=""
TASK_NAME="search-$(date +%s)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt) PROMPT="$2"; shift 2;;
    --output) OUTPUT="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --telegram-group) TELEGRAM_GROUP="$2"; shift 2;;
    --task-name) TASK_NAME="$2"; shift 2;;
    *) echo "Unknown flag: $1"; exit 1;;
  esac
done

if [[ -z "$PROMPT" ]]; then
  echo "ERROR: --prompt is required"
  exit 1
fi

# Default output path
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="${RESULT_DIR}/${TASK_NAME}.md"
fi

mkdir -p "$RESULT_DIR"

# Write task metadata
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if command -v jq &>/dev/null; then
  jq -n \
    --arg name "$TASK_NAME" \
    --arg prompt "$PROMPT" \
    --arg output "$OUTPUT" \
    --arg ts "$STARTED_AT" \
    '{task_name: $name, prompt: $prompt, output: $output, started_at: $ts, status: "running"}' \
    > "${RESULT_DIR}/latest-meta.json"
fi

SEARCH_INSTRUCTION="You are a research assistant. Search the web for the following query.

CRITICAL RULES:
1. Write findings to $OUTPUT INCREMENTALLY — after EACH search, append what you found immediately. Do NOT wait until the end.
2. Start the file with a title and query, then append sections as you discover them.
3. Keep searches focused — max 8 web searches. Synthesize what you have, don't over-research.
4. Include source URLs inline.
5. End with a brief summary section.

Query: $PROMPT

Start by writing the file header NOW, then search and append."

echo "[codex-search] Task: $TASK_NAME"
echo "[codex-search] Output: $OUTPUT"
echo "[codex-search] Model: $MODEL | Timeout: ${TIMEOUT}s"

# Pre-create output file
cat > "$OUTPUT" <<EOF
# Deep Search Report
**Query:** $PROMPT
**Status:** In progress...
---
EOF

# Run Codex — use full-auto sandbox to avoid path permission issues
TIMEOUT_CMD=""
if command -v gtimeout &>/dev/null; then
  TIMEOUT_CMD="gtimeout $TIMEOUT"
elif command -v timeout &>/dev/null; then
  TIMEOUT_CMD="timeout $TIMEOUT"
fi

$TIMEOUT_CMD "$CODEX_BIN" exec \
  --model "$MODEL" \
  --full-auto \
  -c 'model_reasoning_effort="low"' \
  "$SEARCH_INSTRUCTION" 2>&1 | tee "${RESULT_DIR}/task-output.txt"
EXIT_CODE=${PIPESTATUS[0]}

# Append completion marker
if [[ -f "$OUTPUT" ]]; then
  echo -e "\n---\n_Search completed at $(date -u)_" >> "$OUTPUT"
fi

LINES=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Calculate duration (macOS compatible)
END_TS=$(date +%s)
START_TS=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$STARTED_AT" +%s 2>/dev/null || echo "$END_TS")
ELAPSED=$(( END_TS - START_TS ))
MINS=$(( ELAPSED / 60 ))
SECS=$(( ELAPSED % 60 ))
DURATION="${MINS}m${SECS}s"

# Update metadata
if command -v jq &>/dev/null; then
  jq -n \
    --arg name "$TASK_NAME" \
    --arg prompt "$PROMPT" \
    --arg output "$OUTPUT" \
    --arg started "$STARTED_AT" \
    --arg completed "$COMPLETED_AT" \
    --arg duration "$DURATION" \
    --arg lines "$LINES" \
    --argjson exit_code "$EXIT_CODE" \
    '{task_name: $name, prompt: $prompt, output: $output, started_at: $started, completed_at: $completed, duration: $duration, lines: ($lines|tonumber), exit_code: $exit_code, status: (if $exit_code == 0 then "done" elif $exit_code == 124 then "timeout" else "failed" end)}' \
    > "${RESULT_DIR}/latest-meta.json"
fi

echo "[codex-search] Done (${DURATION}, exit=${EXIT_CODE}, ${LINES} lines)"

# ── Send full result content to Telegram ──
if [[ -n "$TELEGRAM_GROUP" ]] && [[ -x "$OPENCLAW_BIN" ]]; then
  STATUS_EMOJI="✅"
  [[ "$EXIT_CODE" == "124" ]] && STATUS_EMOJI="⏱"
  [[ "$EXIT_CODE" != "0" ]] && [[ "$EXIT_CODE" != "124" ]] && STATUS_EMOJI="❌"

  # Read the full result file (truncate at 3500 chars for Telegram message limit)
  FULL_CONTENT=$(cat "$OUTPUT" 2>/dev/null | head -c 3500 || echo "No results")
  TRUNCATED=""
  if [[ $(wc -c < "$OUTPUT" 2>/dev/null || echo 0) -gt 3500 ]]; then
    TRUNCATED="

_(结果已截断，完整内容 ${LINES} 行)_"
  fi

  MSG="${STATUS_EMOJI} *Codex Search 完成* (${DURATION})

${FULL_CONTENT}${TRUNCATED}"

  "$OPENCLAW_BIN" message send \
    --channel telegram \
    --target "$TELEGRAM_GROUP" \
    --message "$MSG" 2>/dev/null || echo "[codex-search] Telegram notification failed"
fi

# ── Wake agent via /hooks/wake ──
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
HOOK_TOKEN=""
if [[ -f "$OPENCLAW_CONFIG" ]]; then
  HOOK_TOKEN=$(python3 -c "import json; c=json.load(open('$OPENCLAW_CONFIG')); print(c.get('hooks',{}).get('token',''))" 2>/dev/null || echo "")
fi

if [[ -n "$HOOK_TOKEN" ]]; then
  WAKE_TEXT="[CODEX_SEARCH_DONE] task=${TASK_NAME} output=${OUTPUT} lines=${LINES} duration=${DURATION} exit=${EXIT_CODE}"
  curl -s -o /dev/null -X POST \
    "http://localhost:${GATEWAY_PORT}/hooks/wake" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${HOOK_TOKEN}" \
    -d "{\"text\":\"${WAKE_TEXT}\",\"mode\":\"now\"}" 2>/dev/null || true
  echo "[codex-search] Wake sent"
else
  echo "[codex-search] No hook token, skipping wake"
fi
