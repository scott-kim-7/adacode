#!/usr/bin/env bash
# Keep MLX server running (auto-restart on crash). Run in a dedicated terminal or background.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${ADA_MLX_LOG:-$ROOT/.ada-mlx-server.log}"
PID_FILE="${ADA_MLX_PID_FILE:-$ROOT/.ada-mlx-server.pid}"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"

stop_existing() {
	"$ROOT/scripts/stop-mlx-server.sh" 2>/dev/null || true
}

trap 'echo "Stopping MLX daemon ..."; stop_existing; exit 0' INT TERM

stop_existing
echo "MLX daemon — model: $MODEL"
echo "  log: $LOG"
echo "  Press Ctrl+C to stop."
echo ""

while true; do
	echo "[$(date '+%H:%M:%S')] Starting MLX ..." | tee -a "$LOG"
	if env ADA_MLX_MODEL="$MODEL" "$ROOT/scripts/serve-qwen.sh" >>"$LOG" 2>&1; then
		echo "[$(date '+%H:%M:%S')] MLX exited cleanly." | tee -a "$LOG"
	else
		echo "[$(date '+%H:%M:%S')] MLX crashed — restarting in 5s ..." | tee -a "$LOG"
	fi
	sleep 5
done
