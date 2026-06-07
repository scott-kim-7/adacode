#!/usr/bin/env bash
# Start a local OpenAI-compatible MLX-VLM server (vision + optional thinking).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

VENV="$ROOT/.venv-mlx"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
MAX_TOKENS="${ADA_MLX_MAX_TOKENS:-4096}"
ENABLE_THINKING="${ADA_MLX_ENABLE_THINKING:-auto}"

if [[ ! -d "$VENV" ]]; then
	"$ROOT/scripts/ensure-mlx-venv.sh"
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

if ! python -c "import mlx_vlm" 2>/dev/null; then
	echo "Missing mlx-vlm — run: ./scripts/ensure-mlx-venv.sh" >&2
	exit 1
fi

USE_THINKING=0
if [[ "$ENABLE_THINKING" == "1" ]] || { [[ "$ENABLE_THINKING" == "auto" ]] && [[ "$MODEL" == *Thinking* ]]; }; then
	USE_THINKING=1
fi

echo "Starting MLX-VLM server (multimodal / vision enabled)"
echo "  model: $MODEL"
echo "  thinking: $([[ $USE_THINKING -eq 1 ]] && echo on || echo off)"
echo "  url:   http://${HOST}:${PORT}/v1/chat/completions"
echo ""

SERVER_ARGS=(
	--model "$MODEL"
	--host "$HOST"
	--port "$PORT"
	--max-tokens "$MAX_TOKENS"
	--trust-remote-code
)
if [[ $USE_THINKING -eq 1 ]]; then
	SERVER_ARGS+=(--enable-thinking)
fi

exec python -m mlx_vlm.server "${SERVER_ARGS[@]}"
