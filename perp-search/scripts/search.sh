#!/usr/bin/env bash
# perp-search — Deep web search via local Perplexica instance
set -euo pipefail

# === Config ===
PERPLEXICA_URL="${PERPLEXICA_URL:-http://localhost:3000}"
RESULT_DIR="/tmp/perp-search-results"
OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || echo openclaw)}"

# Defaults
PROMPT=""
TASK_NAME=""
OUTPUT=""
MODE="balanced"  # speed | balanced | quality
CHAT_PROVIDER=""  # auto-detect from Perplexica API
CHAT_MODEL="openai/gpt-5.2-chat"
EMBED_PROVIDER=""  # auto-detect from Perplexica API
EMBED_MODEL="Xenova/all-MiniLM-L6-v2"
TELEGRAM_GROUP=""
DISCORD_CHANNEL=""
TIMEOUT=120
SOURCES='["web"]'

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt) PROMPT="$2"; shift 2;;
    --task-name) TASK_NAME="$2"; shift 2;;
    --output) OUTPUT="$2"; shift 2;;
    --mode) MODE="$2"; shift 2;;
    --model) CHAT_MODEL="$2"; shift 2;;
    --provider) CHAT_PROVIDER="$2"; shift 2;;
    --telegram-group) TELEGRAM_GROUP="$2"; shift 2;;
    --discord-channel) DISCORD_CHANNEL="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --sources) SOURCES="$2"; shift 2;;
    --url) PERPLEXICA_URL="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

if [[ -z "$PROMPT" ]]; then
  echo "Usage: search.sh --prompt \"query\" [--mode speed|balanced|quality] [--model model] [--timeout 120]"
  exit 1
fi

# Defaults
[[ -z "$TASK_NAME" ]] && TASK_NAME="search-$(date +%s)"
mkdir -p "$RESULT_DIR"
[[ -z "$OUTPUT" ]] && OUTPUT="$RESULT_DIR/$TASK_NAME.md"

# Auto-detect provider IDs if not set
if [[ -z "$CHAT_PROVIDER" || -z "$EMBED_PROVIDER" ]]; then
  PROVIDERS_JSON=$(curl -s "$PERPLEXICA_URL/api/providers" 2>/dev/null || echo '{"providers":[]}')
  if [[ -z "$CHAT_PROVIDER" ]]; then
    CHAT_PROVIDER=$(echo "$PROVIDERS_JSON" | python3 -c "
import json,sys
for p in json.load(sys.stdin).get('providers',[]):
    if any(m.get('key','') == '$CHAT_MODEL' for m in p.get('chatModels',[])):
        print(p['id']); break
" 2>/dev/null)
  fi
  if [[ -z "$EMBED_PROVIDER" ]]; then
    EMBED_PROVIDER=$(echo "$PROVIDERS_JSON" | python3 -c "
import json,sys
for p in json.load(sys.stdin).get('providers',[]):
    if any(m.get('key','') == '$EMBED_MODEL' for m in p.get('embeddingModels',[])):
        print(p['id']); break
" 2>/dev/null)
  fi
fi

if [[ -z "$CHAT_PROVIDER" ]]; then
  echo "[perp-search] ERROR: Could not find provider for model $CHAT_MODEL"
  exit 1
fi
if [[ -z "$EMBED_PROVIDER" ]]; then
  echo "[perp-search] ERROR: Could not find provider for embed model $EMBED_MODEL"
  exit 1
fi

echo "[perp-search] Task: $TASK_NAME"
echo "[perp-search] Mode: $MODE | Model: $CHAT_MODEL"
echo "[perp-search] Output: $OUTPUT"
echo "[perp-search] Timeout: ${TIMEOUT}s"

START=$(date +%s)

# Build JSON payload
PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
    'query': sys.argv[1],
    'sources': json.loads(sys.argv[2]),
    'optimizationMode': sys.argv[3],
    'chatModel': {'providerId': sys.argv[4], 'key': sys.argv[5]},
    'embeddingModel': {'providerId': sys.argv[6], 'key': sys.argv[7]},
    'history': []
}))
" "$PROMPT" "$SOURCES" "$MODE" "$CHAT_PROVIDER" "$CHAT_MODEL" "$EMBED_PROVIDER" "$EMBED_MODEL")

# Call Perplexica API
RESPONSE=$(curl -s --max-time "$TIMEOUT" -X POST "$PERPLEXICA_URL/api/search" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" 2>&1)

END=$(date +%s)
DURATION=$((END - START))

# Parse response
python3 -c "
import json, sys

try:
    data = json.loads(sys.argv[1])
except:
    print('# Search Failed\n\nRaw response:\n\`\`\`\n' + sys.argv[1][:500] + '\n\`\`\`')
    sys.exit(1)

if 'message' not in data or 'sources' not in data:
    error = data.get('message', 'Unknown error')
    print(f'# Search Failed\n\nError: {error}')
    sys.exit(1)

output = f'# {sys.argv[2]}\n\n'
output += f'**Query**: {sys.argv[3]}\n'
output += f'**Mode**: {sys.argv[4]} | **Model**: {sys.argv[5]} | **Duration**: {sys.argv[6]}s\n\n'
output += '---\n\n'
output += data['message']
output += '\n\n---\n\n## Sources\n\n'

for i, s in enumerate(data.get('sources', []), 1):
    meta = s.get('metadata', {})
    title = meta.get('title', 'Unknown')
    url = meta.get('url', '')
    output += f'{i}. [{title}]({url})\n'

print(output)
" "$RESPONSE" "$TASK_NAME" "$PROMPT" "$MODE" "$CHAT_MODEL" "$DURATION" > "$OUTPUT"

EXIT_CODE=$?
LINES=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
SOURCES_COUNT=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(len(d.get('sources',[])))" "$RESPONSE" 2>/dev/null || echo "?")

echo "[perp-search] Done (${DURATION}s, exit=$EXIT_CODE, ${LINES} lines, ${SOURCES_COUNT} sources)"

# Save metadata
cat > "$RESULT_DIR/latest-meta.json" <<METAEOF
{
  "task": "$TASK_NAME",
  "query": $(python3 -c "import json; print(json.dumps('$PROMPT'))"),
  "mode": "$MODE",
  "model": "$CHAT_MODEL",
  "output": "$OUTPUT",
  "duration": $DURATION,
  "sources": $SOURCES_COUNT,
  "exitCode": $EXIT_CODE,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
METAEOF

# Notify via Telegram if configured
if [[ -n "$TELEGRAM_GROUP" ]] && command -v "$OPENCLAW_BIN" &>/dev/null; then
  MSG=$(head -80 "$OUTPUT")
  "$OPENCLAW_BIN" message send \
    --channel telegram --target "$TELEGRAM_GROUP" \
    --message "$MSG" 2>/dev/null || echo "[perp-search] Telegram notification failed"
fi

# Notify via Discord if configured
if [[ -n "$DISCORD_CHANNEL" ]] && command -v "$OPENCLAW_BIN" &>/dev/null; then
  MSG=$(head -80 "$OUTPUT")
  "$OPENCLAW_BIN" message send \
    --channel discord --target "$DISCORD_CHANNEL" \
    --message "$MSG" 2>/dev/null || echo "[perp-search] Discord notification failed"
fi
