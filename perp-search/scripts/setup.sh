#!/usr/bin/env bash
# perp-search setup — Install and configure Perplexica via Docker
set -euo pipefail

CONTAINER_NAME="perplexica"
PORT="${PERPLEXICA_PORT:-3000}"

echo "=== Perplexica Setup ==="

# Check Docker
if ! command -v docker &>/dev/null; then
  echo "Docker not found. Installing..."
  sudo apt-get update -qq && sudo apt-get install -y -qq docker.io
  sudo systemctl start docker && sudo systemctl enable docker
  sudo usermod -aG docker "$USER"
  echo "Docker installed. You may need to re-login for group changes."
fi

# Check if already running
if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' 2>/dev/null | grep -q "$CONTAINER_NAME"; then
  echo "Perplexica already running on port $PORT"
  docker ps --filter "name=$CONTAINER_NAME"
  exit 0
fi

# Remove stopped container if exists
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Pull and run
echo "Starting Perplexica on port $PORT..."
docker run -d \
  -p "$PORT:3000" \
  -v perplexica-data:/home/perplexica/data \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  itzcrazykns1337/perplexica:latest

echo "Waiting for startup..."
sleep 10

# Verify
if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
  echo "✅ Perplexica running at http://localhost:$PORT"
  echo ""
  echo "Next: Configure LLM provider at http://localhost:$PORT"
  echo "Or run: scripts/configure.sh --provider openrouter --api-key YOUR_KEY --model minimax/minimax-m2.5"
else
  echo "❌ Failed to start. Check: docker logs $CONTAINER_NAME"
  exit 1
fi
