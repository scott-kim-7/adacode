#!/usr/bin/env bash
# Stop the background MLX server started by adacode.sh (or anything on ADA_MLX_PORT).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
PID_FILE="${ADA_MLX_PID_FILE:-$ROOT/.ada-mlx-server.pid}"

stopped=0

if [[ -f "$PID_FILE" ]]; then
	pid="$(cat "$PID_FILE" 2>/dev/null || true)"
	if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
		echo "Stopping MLX server (pid $pid) ..."
		kill "$pid" 2>/dev/null || true
		wait "$pid" 2>/dev/null || true
		stopped=1
	fi
	rm -f "$PID_FILE"
fi

if command -v lsof >/dev/null 2>&1; then
	while read -r pid; do
		[[ -z "$pid" ]] && continue
		echo "Stopping process on ${HOST}:${PORT} (pid $pid) ..."
		kill "$pid" 2>/dev/null || true
		stopped=1
	done < <(lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null || true)
fi

if [[ "$stopped" -eq 0 ]]; then
	echo "No MLX server found on port ${PORT}."
else
	echo "MLX server stopped."
fi
