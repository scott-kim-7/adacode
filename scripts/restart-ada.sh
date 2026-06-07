#!/usr/bin/env bash
# Stop and restart MLX + Open WebUI (full stack).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
LOG="$ROOT/.ada-mlx-server.log"

echo "=== Restart Ada stack ==="

"$ROOT/scripts/stop-mlx-server.sh" || true
docker compose -f "$ROOT/web/docker-compose.yml" down 2>/dev/null || docker rm -f adacode-open-webui open-webui 2>/dev/null || true
sleep 1

echo "Starting MLX ($MODEL) ..."
nohup env ADA_MLX_MODEL="$MODEL" "$ROOT/scripts/serve-qwen.sh" >> "$LOG" 2>&1 &
echo $! > "$ROOT/.ada-mlx-server.pid"

for i in $(seq 1 90); do
	if curl -sf "http://127.0.0.1:${ADA_MLX_PORT:-8080}/v1/models" >/dev/null 2>&1; then
		echo "MLX ready."
		break
	fi
	sleep 2
	if [[ $i -eq 90 ]]; then
		echo "MLX failed to start. Log:" >&2
		tail -20 "$LOG" >&2
		exit 1
	fi
done

"$ROOT/scripts/serve-open-webui.sh"

echo ""
echo "Use model: $MODEL"
echo "Open: http://127.0.0.1:${ADA_OPEN_WEBUI_PORT:-3000}"
echo "Tip: do not switch models often — it can crash MLX."
