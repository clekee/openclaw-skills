#!/usr/bin/env bash
# Configure Perplexica LLM provider via config.json
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-perplexica}"
PROVIDER_ID=""
API_KEY=""
BASE_URL=""
MODEL=""
PROVIDER_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider) PROVIDER_ID="$2"; shift 2;;
    --api-key) API_KEY="$2"; shift 2;;
    --base-url) BASE_URL="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --name) PROVIDER_NAME="$2"; shift 2;;
    *) echo "Unknown: $1"; exit 1;;
  esac
done

# Defaults by provider
case "$PROVIDER_ID" in
  openrouter)
    BASE_URL="${BASE_URL:-https://openrouter.ai/api/v1}"
    PROVIDER_NAME="${PROVIDER_NAME:-OpenRouter}"
    ;;
  openai)
    BASE_URL="${BASE_URL:-https://api.openai.com/v1}"
    PROVIDER_NAME="${PROVIDER_NAME:-OpenAI}"
    ;;
  *)
    [[ -z "$BASE_URL" ]] && { echo "--base-url required for custom provider"; exit 1; }
    PROVIDER_NAME="${PROVIDER_NAME:-$PROVIDER_ID}"
    ;;
esac

[[ -z "$API_KEY" ]] && { echo "--api-key required"; exit 1; }
[[ -z "$MODEL" ]] && { echo "--model required"; exit 1; }

echo "Configuring: $PROVIDER_NAME ($PROVIDER_ID)"
echo "  Base URL: $BASE_URL"
echo "  Model: $MODEL"

# Read current config
CONFIG=$(docker exec "$CONTAINER_NAME" cat /home/perplexica/data/config.json)

# Update config
NEW_CONFIG=$(python3 -c "
import json, sys

config = json.loads(sys.argv[1])
provider_id = sys.argv[2]
api_key = sys.argv[3]
base_url = sys.argv[4]
model = sys.argv[5]
name = sys.argv[6]

# Remove existing provider with same id
config['modelProviders'] = [p for p in config['modelProviders'] if p['id'] != provider_id]

# Add new provider
config['modelProviders'].append({
    'id': provider_id,
    'name': name,
    'type': 'openai',
    'chatModels': [{'name': model, 'key': model}],
    'embeddingModels': [],
    'config': {'apiKey': api_key, 'baseURL': base_url},
    'hash': ''
})

config['setupComplete'] = True

# Set as default
config['preferences'] = {
    'chatModel': {'providerId': provider_id, 'key': model},
    'embeddingModel': {
        'providerId': config['modelProviders'][0]['id'],
        'key': 'Xenova/all-MiniLM-L6-v2'
    },
    'optimizationMode': 'balanced',
    'sources': ['web']
}

print(json.dumps(config, indent=2))
" "$CONFIG" "$PROVIDER_ID" "$API_KEY" "$BASE_URL" "$MODEL" "$PROVIDER_NAME")

# Write back
echo "$NEW_CONFIG" | docker exec -i "$CONTAINER_NAME" tee /home/perplexica/data/config.json > /dev/null

# Restart
docker restart "$CONTAINER_NAME" > /dev/null
sleep 5

echo "✅ Configured. Test: curl -s http://localhost:3000/api/providers"
