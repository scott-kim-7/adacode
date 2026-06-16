#!/usr/bin/env bash
# Verify MLX model is present in the Hugging Face cache (no server, no RAM load).
# Requires ADA_MLX_MODEL (Hugging Face repo id).
# Optional: --smoke → one-token chat via running OpenAPI server on :8080.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"
VENV="$ROOT/.venv-mlx"
HOST="$(ada_mlx_host)"
PORT="$(ada_mlx_port)"
SMOKE=0

for arg in "$@"; do
	case "$arg" in
		--smoke) SMOKE=1 ;;
		-h | --help)
			echo "Usage: $0 [--smoke]"
			echo "  Requires ADA_MLX_MODEL (Hugging Face repo id)."
			echo "  --smoke   Call /v1/chat/completions (LLM server must be running on :${PORT})"
			exit 0
			;;
		*)
			echo "Unknown option: $arg" >&2
			exit 2
			;;
	esac
done

if [[ -z "${ADA_MLX_MODEL:-}" ]]; then
	echo "ERROR: Set ADA_MLX_MODEL to the Hugging Face repo id." >&2
	exit 1
fi

MODEL="$ADA_MLX_MODEL"
DISPLAY_NAME="${ADA_MLX_DISPLAY_NAME:-$MODEL}"

if [[ ! -d "$VENV" ]]; then
	echo "Missing $VENV — run: ./scripts/download-mlx-model.sh" >&2
	exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

export ADA_MLX_MODEL="$MODEL"
export ADA_MLX_DISPLAY_NAME="$DISPLAY_NAME"

python "$ROOT/scripts/ada/verify_mlx_cache.py"

if [[ "$SMOKE" -eq 1 ]]; then
	echo ""
	echo "=== Smoke inference (OpenAPI) ==="
	BASE="http://${HOST}:${PORT}"
	ada_require_mlx_up
	MODEL_ID="$(ada_resolve_openai_model "${BASE}/v1")"
	RESP=$(curl -sf "$BASE/v1/chat/completions" \
		-H "Content-Type: application/json" \
		-d "{\"model\":\"${MODEL_ID}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: ok\"}],\"stream\":false,\"max_tokens\":8}")
	echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print('  reply:', d['choices'][0]['message']['content'][:200])"
	echo ""
	echo "RESULT: inference smoke test passed"
fi
