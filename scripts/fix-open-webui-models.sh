#!/usr/bin/env bash
# Ensure MLX is up and Open WebUI can list models (fixes empty/stuck model picker).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
PROXY_PORT="${ADA_MLX_PROXY_PORT:-8081}"
LOG="$ROOT/.ada-mlx-server.log"

mlx_up() {
	curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1
}

echo "=== Fix Open WebUI model list ==="

if ! mlx_up; then
	echo "MLX not running — starting ..."
	nohup env ADA_MLX_MODEL="$MODEL" "$ROOT/scripts/serve-qwen.sh" >> "$LOG" 2>&1 &
	echo $! > "$ROOT/.ada-mlx-server.pid"
	for i in $(seq 1 90); do
		mlx_up && break
		sleep 2
		[[ $i -eq 90 ]] && { echo "MLX failed"; tail -15 "$LOG"; exit 1; }
	done
	echo "MLX ready."
else
	echo "MLX already running."
fi

echo ""
echo "Models on MLX:"
curl -s "http://${HOST}:${PORT}/v1/models" | python3 -c "
import sys, json
target = '${MODEL}'
for item in json.load(sys.stdin)['data']:
    mark = '  ← default' if item['id'] == target else ''
    print(f\"  {item['id']}{mark}\")
"

"$ROOT/scripts/ensure-mlx-proxy.sh" --force

export ADA_MLX_MODEL="$MODEL"
export OPENAI_API_BASE_URL="http://host.docker.internal:${PROXY_PORT}/v1"
export OPENAI_API_KEY=local

echo ""
echo "Recreating Open WebUI container (OpenAI URL → :${PROXY_PORT} proxy) ..."
docker compose -f "$ROOT/web/docker-compose.yml" up -d --force-recreate

for i in $(seq 1 30); do
	curl -sf "http://127.0.0.1:${ADA_OPEN_WEBUI_PORT:-3000}/" >/dev/null 2>&1 && break
	sleep 2
done

if docker exec "${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}" \
	curl -sf --connect-timeout 5 "http://host.docker.internal:${PROXY_PORT}/v1/models" >/dev/null 2>&1; then
	echo "Open WebUI → MLX proxy (:${PROXY_PORT}): OK"
else
	echo "Open WebUI → MLX proxy: FAILED (run ./scripts/ensure-mlx-proxy.sh)" >&2
	exit 1
fi

echo ""
echo "Done. In the browser:"
echo "  1. Hard refresh http://127.0.0.1:${ADA_OPEN_WEBUI_PORT:-3000} (Cmd+Shift+R)"
echo "  2. Start a NEW chat (+)"
echo "  3. Model picker → search: Qwen3-VL-32B"
echo "  4. Pick: ${MODEL}"
echo ""
echo "If the list is still empty:"
echo "  Admin (gear) → Settings → Connections → OpenAI"
echo "    URL:  http://host.docker.internal:${PROXY_PORT}/v1"
echo "    Key:  local  → Save → Refresh model list"
echo ""
echo "If replies are blank, start a NEW chat (+). Old chats may have saved empty answers."
