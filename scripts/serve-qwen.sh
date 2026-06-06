#!/usr/bin/env bash
# Start a local OpenAI-compatible MLX server for Qwen2.5-VL-72B (Step 1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv-mlx"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MODEL="${ADA_MLX_MODEL:-mlx-community/Qwen2.5-VL-72B-Instruct-4bit}"

if [[ ! -d "$VENV" ]]; then
	echo "Missing $VENV — run: python3 -m venv .venv-mlx && source .venv-mlx/bin/activate && pip install -U mlx-lm" >&2
	exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

echo "Starting MLX server"
echo "  model: $MODEL"
echo "  url:   http://${HOST}:${PORT}/v1/chat/completions"
echo ""

exec python -m mlx_lm server \
	--model "$MODEL" \
	--host "$HOST" \
	--port "$PORT"
