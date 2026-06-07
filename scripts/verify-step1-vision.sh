#!/usr/bin/env bash
# Smoke-test multimodal (image) chat via the local MLX VLM server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
BASE="http://${HOST}:${PORT}"

echo "Checking MLX vision at $BASE ..."

if ! curl -sf "$BASE/v1/models" >/dev/null; then
	echo "MLX server not running. Start: ./scripts/serve-qwen.sh" >&2
	exit 1
fi

export ADA_MLX_HOST="$HOST"
export ADA_MLX_PORT="$PORT"
export ADA_MLX_MODEL="$MODEL"

# shellcheck source=/dev/null
source "$ROOT/.venv-mlx/bin/activate"
python "$ROOT/scripts/ada/verify_mlx_vision.py"
