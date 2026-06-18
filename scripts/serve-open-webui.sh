#!/usr/bin/env bash
# Open WebUI (Docker) → local MLX OpenAI API via web/docker-compose.yml
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/web/docker-compose.yml"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

MLX_HOST="${ADA_MLX_HOST:-127.0.0.1}"
MLX_PORT="${ADA_MLX_PORT:-8080}"
WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
CONTAINER_NAME="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"

mlx_url() {
	echo "http://${MLX_HOST}:${MLX_PORT}"
}

mlx_healthy() {
	curl -sf "$(mlx_url)/v1/models" >/dev/null 2>&1
}

if ! command -v docker >/dev/null 2>&1; then
	echo "Docker is required for Open WebUI. Start Docker Desktop first." >&2
	exit 1
fi

if ! docker info >/dev/null 2>&1; then
	echo "Docker daemon is not running. Start Docker Desktop and retry." >&2
	exit 1
fi

AGENT_PORT="${ADA_AGENT_PORT:-9082}"

if [[ ! -d "$ROOT/web/open-webui/.git" ]]; then
	echo "Vendoring Open WebUI v0.6.42 with Ada overlays ..."
	"$ROOT/scripts/vendor-open-webui.sh"
else
	OVERLAY="${ROOT}/web/open-webui-overlays"
	STAMP="${ROOT}/web/open-webui/.ada-overlay-stamp"
	need_vendor=0
	if [[ "${ADA_FORCE_VENDOR:-0}" == "1" ]]; then
		need_vendor=1
	elif [[ ! -f "$STAMP" ]]; then
		need_vendor=1
	elif [[ "$OVERLAY" -nt "$STAMP" ]]; then
		need_vendor=1
	fi
	if [[ "$need_vendor" == "1" ]]; then
		echo "Ada overlays changed — re-vendoring Open WebUI ..."
		"$ROOT/scripts/vendor-open-webui.sh"
	fi
fi

if ! mlx_healthy; then
	echo "WARNING: MLX server is not running at $(mlx_url) — continuing (start mlx_vlm when ready)" >&2
fi

"$ROOT/scripts/ensure-ada-agent-server.sh"

OPENAI_BASE="http://host.docker.internal:${AGENT_PORT}/v1"
if [[ "$(uname -s)" == "Linux" ]]; then
	OPENAI_BASE="http://${MLX_HOST}:${AGENT_PORT}/v1"
	if [[ "$MLX_HOST" == "127.0.0.1" || "$MLX_HOST" == "localhost" ]]; then
		OPENAI_BASE="http://172.17.0.1:${AGENT_PORT}/v1"
	fi
fi

AGENT_BASE="http://host.docker.internal:${AGENT_PORT}"
if [[ "$(uname -s)" == "Linux" ]]; then
	AGENT_BASE="http://${MLX_HOST}:${AGENT_PORT}"
	if [[ "$MLX_HOST" == "127.0.0.1" || "$MLX_HOST" == "localhost" ]]; then
		AGENT_BASE="http://172.17.0.1:${AGENT_PORT}"
	fi
fi

export ADA_OPEN_WEBUI_PORT="$WEBUI_PORT"
export ADA_OPEN_WEBUI_CONTAINER="$CONTAINER_NAME"
export OPENAI_API_BASE_URL="$OPENAI_BASE"
export ADA_AGENT_BASE_URL="$AGENT_BASE"
export OPENAI_API_KEY=local
ada_export_webui_model_env

if [[ "${ADA_OPEN_WEBUI_RESET_DATA:-0}" == "1" ]]; then
	echo "ADA_OPEN_WEBUI_RESET_DATA=1 — resetting Open WebUI data volume ..."
	"$ROOT/scripts/reset-open-webui-data.sh"
fi

# Remove stale container that failed to bind the port (STATUS=Created)
if docker ps -a --format '{{.Names}} {{.Status}}' | grep -q "^${CONTAINER_NAME} Created"; then
	echo "Removing stale container ${CONTAINER_NAME} (port bind failed previously) ..."
	docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# Port conflict: another container already on WEBUI_PORT
if lsof -iTCP:"${WEBUI_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
	other="$(docker ps --format '{{.Names}}' --filter "publish=${WEBUI_PORT}" 2>/dev/null | head -1 || true)"
	if [[ -n "$other" && "$other" != "$CONTAINER_NAME" ]]; then
		echo "Port ${WEBUI_PORT} is used by Docker container: ${other}" >&2
		echo "Stop it and retry:" >&2
		echo "  docker rm -f ${other}" >&2
		echo "Or use another port:" >&2
		echo "  ADA_OPEN_WEBUI_PORT=3001 ./scripts/serve-open-webui.sh" >&2
		exit 1
	fi
fi

echo "Starting Open WebUI on http://127.0.0.1:${WEBUI_PORT}"
echo "  compose: ${COMPOSE_FILE}"
echo "  Agent API: ${OPENAI_BASE} (LangGraph → MLX)"
echo "  models:  OpenAPI via Agent /v1/models"
if [[ -n "${DEFAULT_MODELS:-}" ]]; then
	echo "  default: ${DEFAULT_MODELS} (from mlx_vlm loaded_model)"
else
	echo "  default: (none — start mlx_vlm with --model, then ./scripts/fix-open-webui-models.sh)"
fi
echo ""
echo "First login: create a local account (data stays on your machine)."
echo "Stop with: docker compose -f ${COMPOSE_FILE} down"
echo ""

docker compose -f "$COMPOSE_FILE" build open-webui
docker compose -f "$COMPOSE_FILE" up -d --force-recreate

echo "Waiting for Open WebUI to become ready ..."
	for ((i = 1; i <= 60; i++)); do
	if curl -sf "http://127.0.0.1:${WEBUI_PORT}/" >/dev/null 2>&1; then
		break
	fi
	sleep 2
	if [[ $i -eq 60 ]]; then
		echo "Open WebUI did not respond on port ${WEBUI_PORT}. Check logs:" >&2
		echo "  docker logs ${CONTAINER_NAME}" >&2
		if docker logs "$CONTAINER_NAME" 2>&1 | grep -qE 'b2c3d4e5f6a7|access_control|Can.t locate revision'; then
			echo "" >&2
			echo "Likely cause: old data from ghcr.io/open-webui:main is incompatible with v0.6.42." >&2
			echo "Fix: ADA_OPEN_WEBUI_RESET_DATA=1 ./scripts/ada.sh start" >&2
			echo "  or: ./scripts/reset-open-webui-data.sh && ./scripts/serve-open-webui.sh" >&2
		fi
		exit 1
	fi
done

# Align DEFAULT_MODELS env + webui.db with mlx_vlm loaded_model.
ada_sync_model_on_restart || true

if docker exec "$CONTAINER_NAME" curl -sf --connect-timeout 5 "http://host.docker.internal:${AGENT_PORT}/v1/models" >/dev/null 2>&1; then
	echo "Open WebUI → LangGraph agent connectivity OK"
else
	echo "WARNING: Open WebUI cannot reach agent API at host.docker.internal:${AGENT_PORT}" >&2
	echo "Run: ./scripts/ensure-ada-agent-server.sh" >&2
fi

if command -v open >/dev/null 2>&1; then
	open "http://127.0.0.1:${WEBUI_PORT}"
fi

echo "Open WebUI running."
