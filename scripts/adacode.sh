#!/usr/bin/env bash
# Launch adacode: local Qwen MLX server (background) + Code-OSS IDE.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

USER_DIR="$("$ROOT/scripts/resolve-vscode-user-dir.sh")"
CHAT_MODELS="$USER_DIR/chatLanguageModels.json"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MLX_LOG="${ADA_MLX_LOG:-$ROOT/.ada-mlx-server.log}"
MLX_PID_FILE="${ADA_MLX_PID_FILE:-$ROOT/.ada-mlx-server.pid}"
STARTED_MLX=0
MLX_PID=""

cleanup() {
	if [[ "$STARTED_MLX" -eq 1 && -n "$MLX_PID" ]]; then
		echo ""
		echo "Stopping MLX server (pid $MLX_PID) ..."
		kill "$MLX_PID" 2>/dev/null || true
		wait "$MLX_PID" 2>/dev/null || true
		rm -f "$MLX_PID_FILE"
	fi
}
trap cleanup EXIT INT TERM

mlx_healthy() {
	curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1
}

wait_for_mlx() {
	local tries="${ADA_MLX_WAIT_TRIES:-120}"
	for ((i = 1; i <= tries; i++)); do
		if mlx_healthy; then
			return 0
		fi
		if [[ $i -eq 1 || $((i % 10)) -eq 0 ]]; then
			echo "Waiting for MLX server (http://${HOST}:${PORT}) ... ${i}/${tries}"
		fi
		sleep 2
	done
	echo "MLX server did not become ready. See $MLX_LOG" >&2
	return 1
}

ensure_node() {
	if [[ -f "$HOME/.nvm/nvm.sh" ]]; then
		# shellcheck source=/dev/null
		export NVM_DIR="$HOME/.nvm"
		# shellcheck source=/dev/null
		. "$NVM_DIR/nvm.sh"
		nvm use 24.15.0 >/dev/null
	fi
}

mlx_supports_vision() {
	# shellcheck source=/dev/null
	source "$ROOT/.venv-mlx/bin/activate" 2>/dev/null || return 1
	export ADA_MLX_HOST="$HOST" ADA_MLX_PORT="$PORT"
	python "$ROOT/scripts/ada/verify_mlx_vision.py" >/dev/null 2>&1
}

ensure_mlx_venv() {
	"$ROOT/scripts/ensure-mlx-venv.sh"
	# shellcheck source=/dev/null
	source "$ROOT/.venv-mlx/bin/activate"
}

ensure_chat_models() {
	if [[ ! -f "$CHAT_MODELS" ]] || ! grep -q "$ADA_MLX_BYOK_ID_MARKER" "$CHAT_MODELS" 2>/dev/null; then
		echo "Running Step 1 setup (BYOK + settings) ..."
		"$ROOT/scripts/install-step1.sh"
	fi
	# Ensure agent mode setting even if chatLanguageModels already existed
	if [[ ! -f "${USER_DIR}/settings.json" ]] \
		|| ! grep -q '"chat.agent.enabled": true' "${USER_DIR}/settings.json" 2>/dev/null; then
		"$ROOT/scripts/install-step1.sh"
	fi
}

start_mlx_if_needed() {
	if mlx_healthy; then
		if mlx_supports_vision; then
			echo "MLX-VLM server already running at http://${HOST}:${PORT} (vision OK)"
			return 0
		fi
		echo "Replacing text-only mlx_lm server with mlx-vlm (vision) ..."
		"$ROOT/scripts/stop-mlx-server.sh" || true
	fi

	echo "Starting MLX-VLM server in background (log: $MLX_LOG) ..."
	: >"$MLX_LOG"
	nohup env ADA_MLX_HOST="$HOST" ADA_MLX_PORT="$PORT" ADA_MLX_MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}" \
		"$ROOT/scripts/serve-qwen.sh" >>"$MLX_LOG" 2>&1 &
	MLX_PID=$!
	echo "$MLX_PID" >"$MLX_PID_FILE"
	STARTED_MLX=1
	wait_for_mlx
}

ensure_node
ensure_mlx_venv
ensure_chat_models
start_mlx_if_needed

echo "Launching adacode IDE ..."
echo "  Chat model: ${ADA_MLX_DISPLAY_NAME_DEFAULT} → Other Models"
echo "  Vision: mlx-vlm server (image attach supported)"
echo "  Image note: first reply can take 30-90s on Qwen VL 32B - wait for the response."
echo "  Tip: use #filename in chat for file context; Ask mode for image Q&A, Agent for tools."
echo ""

export ADA_FORCE_BYOK=1
exec "$ROOT/scripts/code.sh" "$@"
