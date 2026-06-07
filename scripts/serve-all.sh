#!/usr/bin/env bash
# Start MLX (daemon) + Open WebUI — recommended one-command stack.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${ADA_MLX_LOG:-$ROOT/.ada-mlx-server.log}"
PID_FILE="${ADA_MLX_DAEMON_PID:-$ROOT/.ada-mlx-daemon.pid}"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"

mlx_up() {
	curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1
}

echo "=== Ada stack: MLX + Open WebUI ==="

# Stop old daemon if any
if [[ -f "$PID_FILE" ]]; then
	old="$(cat "$PID_FILE" 2>/dev/null || true)"
	[[ -n "$old" ]] && kill "$old" 2>/dev/null || true
	rm -f "$PID_FILE"
fi
"$ROOT/scripts/stop-mlx-server.sh" 2>/dev/null || true

# Start MLX (simple background — keep this terminal job alive via nohup)
nohup env ADA_MLX_MODEL="$MODEL" "$ROOT/scripts/serve-qwen.sh" >>"$LOG" 2>&1 &
echo $! > "$ROOT/.ada-mlx-server.pid"
echo "MLX pid $(cat "$ROOT/.ada-mlx-server.pid") (log: $LOG)"

echo -n "Waiting for MLX"
for i in $(seq 1 90); do
	if mlx_up; then
		echo " ready."
		break
	fi
	echo -n "."
	sleep 2
	if [[ $i -eq 90 ]]; then
		echo " FAILED" >&2
		tail -20 "$LOG" >&2
		exit 1
	fi
done

export ADA_MLX_MODEL="$MODEL"
"$ROOT/scripts/serve-open-webui.sh"

echo ""
echo "Stack running."
echo "  MLX:      http://${HOST}:${PORT}/v1  ($MODEL)"
echo "  Web UI:   http://127.0.0.1:${ADA_OPEN_WEBUI_PORT:-3000}"
echo ""
echo "In browser: Cmd+Shift+R → New chat → pick $MODEL"
echo "Stop MLX daemon: kill \$(cat $PID_FILE) && ./scripts/stop-mlx-server.sh"
echo "Stop WebUI: docker compose -f web/docker-compose.yml down"
