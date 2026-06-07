#!/usr/bin/env bash
# One-shot: ensure MLX is up, then start Open WebUI (Docker).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"

mlx_healthy() {
	curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1
}

if ! mlx_healthy; then
	echo "MLX server not running — starting in background..."
	"$ROOT/scripts/serve-qwen.sh" &
	MLX_PID=$!
	trap 'kill "$MLX_PID" 2>/dev/null || true' EXIT

	echo "Waiting for MLX at http://${HOST}:${PORT} ..."
	for ((i = 1; i <= 120; i++)); do
		if mlx_healthy; then
			echo "MLX ready."
			break
		fi
		sleep 2
		if [[ $i -eq 120 ]]; then
			echo "MLX did not become ready in time." >&2
			exit 1
		fi
	done
	trap - EXIT
fi

export ADA_MLX_HOST="$HOST" ADA_MLX_PORT="$PORT"
export ADA_OPEN_WEBUI_PORT="$WEBUI_PORT"
exec "$ROOT/scripts/serve-open-webui.sh"
