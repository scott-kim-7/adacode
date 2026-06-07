#!/usr/bin/env bash
# Stop MLX server and start it again (background by default).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
LOG="${ADA_MLX_LOG:-$ROOT/.ada-mlx-server.log}"
PID_FILE="${ADA_MLX_PID_FILE:-$ROOT/.ada-mlx-server.pid}"
DAEMON_PID_FILE="${ADA_MLX_DAEMON_PID:-$ROOT/.ada-mlx-daemon.pid}"
FOREGROUND=0

usage() {
	echo "Usage: $0 [--foreground|-f]" >&2
	echo "  Stop MLX on :${PORT}, then start again." >&2
	echo "  Default: background (nohup). Use -f to run in this terminal." >&2
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	-f | --foreground)
		FOREGROUND=1
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		echo "Unknown option: $1" >&2
		usage
		exit 1
		;;
	esac
done

mlx_up() {
	curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1
}

echo "=== Restart MLX ==="

# Stop MLX daemon wrapper if present
if [[ -f "$DAEMON_PID_FILE" ]]; then
	dpid="$(cat "$DAEMON_PID_FILE" 2>/dev/null || true)"
	if [[ -n "$dpid" ]] && kill -0 "$dpid" 2>/dev/null; then
		echo "Stopping MLX daemon (pid $dpid) ..."
		kill "$dpid" 2>/dev/null || true
	fi
	rm -f "$DAEMON_PID_FILE"
fi

"$ROOT/scripts/stop-mlx-server.sh" || true
if [[ -f "${ADA_MLX_PROXY_PID:-$ROOT/.ada-mlx-proxy.pid}" ]]; then
	ppid="$(cat "${ADA_MLX_PROXY_PID:-$ROOT/.ada-mlx-proxy.pid}" 2>/dev/null || true)"
	[[ -n "$ppid" ]] && kill "$ppid" 2>/dev/null || true
	rm -f "${ADA_MLX_PROXY_PID:-$ROOT/.ada-mlx-proxy.pid}"
fi
sleep 1

if [[ "$FOREGROUND" -eq 1 ]]; then
	echo "Starting MLX in foreground ($MODEL) ..."
	echo "  url: http://${HOST}:${PORT}/v1"
	echo "  Press Ctrl+C to stop."
	echo ""
	exec env ADA_MLX_MODEL="$MODEL" "$ROOT/scripts/serve-qwen.sh"
fi

echo "Starting MLX in background ($MODEL) ..."
nohup env ADA_MLX_MODEL="$MODEL" "$ROOT/scripts/serve-qwen.sh" >>"$LOG" 2>&1 &
echo $! > "$PID_FILE"
echo "  pid: $(cat "$PID_FILE")"
echo "  log: $LOG"

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
		echo "Last log lines:" >&2
		tail -20 "$LOG" >&2
		exit 1
	fi
done

"$ROOT/scripts/ensure-mlx-proxy.sh"

echo ""
echo "MLX running at http://${HOST}:${PORT}/v1"
echo "  model: $MODEL"
echo "Stop: ./scripts/stop-mlx-server.sh"
