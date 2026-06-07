#!/usr/bin/env bash
# Smoke-test the local MLX OpenAI-compatible server (Step 1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
BASE="http://${HOST}:${PORT}"

echo "Checking MLX server at $BASE ..."

curl -sf "$BASE/v1/models" | head -c 500
echo ""
echo ""

RESP=$(curl -sf "$BASE/v1/chat/completions" \
	-H "Content-Type: application/json" \
	-d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hi in one word.\"}],\"stream\":false,\"max_tokens\":16}")

echo "$RESP" | head -c 800
echo ""
echo ""
echo "Step 1 MLX smoke test passed."
