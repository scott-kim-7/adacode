#!/usr/bin/env bash
# Ensure MLX is up and Open WebUI model name matches mlx_vlm --model (loaded_model).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="$(ada_mlx_host)"
PORT="$(ada_mlx_port)"
AGENT_PORT="${ADA_AGENT_PORT:-8082}"

echo "=== Fix Open WebUI model list ==="

ada_require_mlx_up

echo ""
echo "Models on MLX (OpenAPI):"
curl -s "http://${HOST}:${PORT}/v1/models" | python3 -c "
import json, sys
for item in json.load(sys.stdin).get('data', []):
    print(f\"  {item.get('id', '')}\")
"

"$ROOT/scripts/ensure-ada-agent-server.sh" --force

export OPENAI_API_BASE_URL="http://host.docker.internal:${AGENT_PORT}/v1"
export OPENAI_API_KEY=local
export ADA_OPEN_WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
export ADA_OPEN_WEBUI_CONTAINER="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"

echo ""
echo "Recreating Open WebUI container (OpenAI URL → :${AGENT_PORT} LangGraph agent) ..."
docker compose -f "$ROOT/web/docker-compose.yml" up -d --force-recreate

ada_wait_webui_up "${ADA_OPEN_WEBUI_PORT}" 30
ada_sync_model_on_restart

if docker exec "${ADA_OPEN_WEBUI_CONTAINER}" \
	curl -sf --connect-timeout 5 "http://host.docker.internal:${AGENT_PORT}/v1/models" >/dev/null 2>&1; then
	echo "Open WebUI → LangGraph agent (:${AGENT_PORT}): OK"
else
	echo "Open WebUI → agent API: FAILED (run ./scripts/ensure-ada-agent-server.sh)" >&2
	exit 1
fi

echo ""
echo "Done. In the browser:"
echo "  1. Hard refresh http://127.0.0.1:${ADA_OPEN_WEBUI_PORT} (Cmd+Shift+R)"
echo "  2. Start a NEW chat (+)"
if [[ -n "${DEFAULT_MODELS:-}" ]]; then
	echo "  3. Default model should be: ${DEFAULT_MODELS}"
else
	echo "  3. Start mlx_vlm with --model, then run this script again"
fi
