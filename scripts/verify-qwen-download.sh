#!/usr/bin/env bash
# Verify Step 1 MLX model is present in the Hugging Face cache (no server, no RAM load).
# Optional: --smoke  → also run one-token chat via a running MLX server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv-mlx"
MODEL="${ADA_MLX_MODEL:-mlx-community/Qwen2.5-VL-72B-Instruct-4bit}"
DISPLAY_NAME="${ADA_MLX_DISPLAY_NAME:-Qwen2.5-VL-72B-Instruct (MLX 4-bit)}"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
SMOKE=0

for arg in "$@"; do
	case "$arg" in
		--smoke) SMOKE=1 ;;
		-h | --help)
			echo "Usage: $0 [--smoke]"
			echo "  (default) Check HF cache files for $MODEL"
			echo "  --smoke   Also call http://${HOST}:${PORT}/v1/chat/completions (server must be running)"
			exit 0
			;;
		*)
			echo "Unknown option: $arg" >&2
			exit 2
			;;
	esac
done

if [[ ! -d "$VENV" ]]; then
	echo "Missing $VENV — run: ./scripts/download-qwen-model.sh" >&2
	exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

export ADA_MLX_MODEL="$MODEL"
export ADA_MLX_DISPLAY_NAME="$DISPLAY_NAME"

python "$ROOT/scripts/ada/verify_mlx_cache.py"

if [[ "$SMOKE" -eq 1 ]]; then
	echo ""
	echo "=== Smoke inference (MLX server) ==="
	BASE="http://${HOST}:${PORT}"
	if ! curl -sf "$BASE/v1/models" >/dev/null; then
		echo "MLX server not running at $BASE" >&2
		echo "Start with: ./scripts/serve-qwen.sh  (or ./scripts/adacode.sh)" >&2
		exit 1
	fi
	RESP=$(curl -sf "$BASE/v1/chat/completions" \
		-H "Content-Type: application/json" \
		-d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: ok\"}],\"stream\":false,\"max_tokens\":8}")
	echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print('  reply:', d['choices'][0]['message']['content'][:200])"
	echo ""
	echo "RESULT: inference smoke test passed"
fi
