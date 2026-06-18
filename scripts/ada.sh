#!/usr/bin/env bash
# Ada web stack: stop / start / restart Agent + Open WebUI (MLX :8089 must already be running).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"
# shellcheck source=ada/prompt_secrets.sh
source "$ROOT/scripts/ada/prompt_secrets.sh"

HOST="$(ada_mlx_host)"
MLX_PORT="$(ada_mlx_port)"
AGENT_PORT="${ADA_AGENT_PORT:-9082}"
WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
CONTAINER="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"
COMPOSE_FILE="$ROOT/web/docker-compose.yml"
AGENT_PID_FILE="${ADA_AGENT_PID:-$ROOT/.ada-agent-server.pid}"
AGENT_SCRIPT="$ROOT/scripts/ada_agent_server.py"

usage() {
	cat <<EOF
Usage: $(basename "$0") [command]

Commands:
  restart   Stop Agent + WebUI, then start fresh (default)
  start     Start Agent + Open WebUI (MLX on :${MLX_PORT} must already be up)
  stop      Stop Open WebUI and Agent API (does not stop MLX)
  status    Show whether MLX, Agent, and WebUI are up

Prerequisite:
  LLM server (mlx_vlm.server / mlx_lm) at http://${HOST}:${MLX_PORT}
  — verified via /health or /v1/models (waits up to ${ADA_MLX_WAIT_SEC:-30}s)

Environment (optional):
  ADA_MLX_PORT               MLX OpenAI API port (default: 8089)
  ADA_AGENT_PORT             LangGraph OpenAI API port (default: 9082)
  ADA_OPEN_WEBUI_PORT        Browser UI port (default: 3000)

Ada Email / vault (start/restart):
  Vault password: prompted when ada/vault/secrets.vault.enc exists (passed to Agent via fd 3, not stored).
  Automation: printf '%s' "$VAULT_PASS" | ADA_NON_INTERACTIVE=1 ADA_VAULT_UNLOCK_FD=3 ./scripts/ada.sh start 3<&0

Examples:
  ./scripts/ada.sh
  ./scripts/ada.sh stop
  ./scripts/ada.sh start
EOF
}

port_pids() {
	local port="$1"
	if command -v lsof >/dev/null 2>&1; then
		lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true
	fi
}

kill_pid_file() {
	local pid_file="$1"
	local label="$2"
	if [[ ! -f "$pid_file" ]]; then
		return 0
	fi
	local pid
	pid="$(cat "$pid_file" 2>/dev/null || true)"
	rm -f "$pid_file"
	if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
		echo "Stopping ${label} (pid ${pid}) ..."
		kill "$pid" 2>/dev/null || true
		wait "$pid" 2>/dev/null || true
	fi
}

kill_port_listeners() {
	local port="$1"
	local label="$2"
	local pid
	while read -r pid; do
		[[ -z "$pid" ]] && continue
		echo "Stopping ${label} on :${port} (pid ${pid}) ..."
		kill "$pid" 2>/dev/null || true
	done < <(port_pids "$port")
}

stop_webui() {
	echo "[1/2] Open WebUI"
	if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
		docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
		docker rm -f "$CONTAINER" open-webui >/dev/null 2>&1 || true
	fi
	if curl -sf "http://127.0.0.1:${WEBUI_PORT}/" >/dev/null 2>&1; then
		echo "  WARNING: something still responds on :${WEBUI_PORT}" >&2
	else
		echo "  stopped (:${WEBUI_PORT} free)"
	fi
}

stop_agent() {
	echo "[2/2] LangGraph agent API"
	kill_pid_file "$AGENT_PID_FILE" "agent server"
	pkill -f "$AGENT_SCRIPT" 2>/dev/null || true
	kill_port_listeners "$AGENT_PORT" "agent server"
	sleep 1
	if curl -sf "http://${HOST}:${AGENT_PORT}/v1/models" >/dev/null 2>&1; then
		echo "  WARNING: agent still responds on :${AGENT_PORT}" >&2
	else
		echo "  stopped (:${AGENT_PORT} free)"
	fi
}

stop_all() {
	echo "=== Stop Ada stack (Agent + WebUI; MLX unchanged) ==="
	stop_webui
	stop_agent
	echo ""
	echo "Ada Agent and WebUI stopped. MLX on :${MLX_PORT} was not touched."
}

mlx_up() {
	ada_mlx_up
}

agent_up() {
	curl -sf "http://${HOST}:${AGENT_PORT}/health" >/dev/null 2>&1
}

webui_up() {
	curl -sf "http://127.0.0.1:${WEBUI_PORT}/" >/dev/null 2>&1
}

start_agent() {
	echo "[1/2] LangGraph agent API (:${AGENT_PORT})"
	if [[ -n "${_ADA_PROMPT_VAULT_PASSWORD:-}" ]]; then
		ADA_VAULT_UNLOCK_FD=3 "$ROOT/scripts/ensure-ada-agent-server.sh" --force \
			3<<<"$_ADA_PROMPT_VAULT_PASSWORD"
	elif [[ "${ADA_NON_INTERACTIVE:-0}" == "1" && -n "${ADA_VAULT_UNLOCK_FD:-}" ]]; then
		ADA_VAULT_UNLOCK_FD="${ADA_VAULT_UNLOCK_FD}" "$ROOT/scripts/ensure-ada-agent-server.sh" --force 3<&3
	else
		"$ROOT/scripts/ensure-ada-agent-server.sh" --force
	fi
	unset _ADA_PROMPT_VAULT_PASSWORD
}

start_webui() {
	echo "[2/2] Open WebUI (:${WEBUI_PORT})"
	export ADA_MLX_HOST="$HOST"
	export ADA_MLX_PORT="$MLX_PORT"
	export ADA_OPEN_WEBUI_PORT="$WEBUI_PORT"
	export ADA_OPEN_WEBUI_CONTAINER="$CONTAINER"
	"$ROOT/scripts/serve-open-webui.sh"
}

start_all() {
	echo "=== Start Ada stack ==="
	if ! ada_prompt_secrets "$ROOT"; then
		exit 1
	fi
	if ada_mlx_up; then
		MODEL_ID="$(ada_resolve_openai_model "$(ada_mlx_url)/v1" 2>/dev/null || true)"
	else
		ada_warn_mlx_up || true
		MODEL_ID=""
	fi
	if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
		echo "Docker Desktop is not running. Start it, then retry." >&2
		exit 1
	fi
	start_agent
	start_webui
	ada_clear_prompt_secrets
	ada_sync_model_on_restart || true
	echo ""
	echo "Ada stack is running."
	echo "  MLX:    $(ada_mlx_url)/v1  (external — not managed by Ada)"
	echo "  Agent:  http://${HOST}:${AGENT_PORT}/v1  (LangGraph → MLX)"
	echo "  UI:     http://127.0.0.1:${WEBUI_PORT}"
	echo "  Models: OpenAPI GET $(ada_mlx_url)/v1/models"
	if [[ -n "$MODEL_ID" ]]; then
		echo "  Loaded: ${MODEL_ID}"
	elif ada_mlx_up; then
		echo "  Loaded: (none yet — select a model in Open WebUI)"
	else
		echo "  MLX:    not reachable — start mlx_vlm.server on :${MLX_PORT}"
	fi
	echo ""
	echo "Open a NEW chat in the browser (model list from Agent API)."
	echo "Ada Email: Admin → Settings → Ada Email (API key synced from ada.sh)."
}

status_line() {
	local name="$1"
	local ok="$2"
	local detail="$3"
	if [[ "$ok" -eq 1 ]]; then
		printf "  OK   %-18s %s\n" "$name" "$detail"
	else
		printf "  DOWN %-18s %s\n" "$name" "$detail"
	fi
}

status_all() {
	echo "=== Ada stack status ==="
	local mlx_ok=0 agent_ok=0 webui_ok=0 docker_ok=0
	mlx_up && mlx_ok=1
	agent_up && agent_ok=1
	webui_up && webui_ok=1
	if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
		docker_ok=1
	fi
	status_line "MLX :${MLX_PORT}" "$mlx_ok" "external LLM server"
	status_line "Agent :${AGENT_PORT}" "$agent_ok" "Open WebUI → LangGraph"
	status_line "WebUI :${WEBUI_PORT}" "$webui_ok" "http://127.0.0.1:${WEBUI_PORT}"
	status_line "Docker ${CONTAINER}" "$docker_ok" "$(docker ps --filter "name=${CONTAINER}" --format '{{.Status}}' 2>/dev/null || echo 'not running')"
	local model_id=""
	if mlx_ok; then
		model_id="$(ada_default_model_id 2>/dev/null || true)"
	fi
	if [[ -n "$model_id" ]]; then
		printf "  MLX  loaded_model     %s\n" "$model_id"
	fi
	echo ""
	if [[ "$mlx_ok$agent_ok$webui_ok" == "111" ]]; then
		echo "Ready. Use a NEW chat after restart."
	elif [[ "$mlx_ok" -eq 0 ]]; then
		echo "MLX is down. Start the LLM server on :${MLX_PORT}, then: ./scripts/ada.sh start"
	else
		echo "Not fully up. Run: ./scripts/ada.sh restart"
	fi
}

main() {
	local cmd="${1:-restart}"
	case "$cmd" in
	restart)
		stop_all
		sleep 2
		start_all
		;;
	start)
		start_all
		;;
	stop)
		stop_all
		;;
	status | st)
		status_all
		;;
	-h | --help | help)
		usage
		;;
	*)
		echo "Unknown command: $cmd" >&2
		usage
		exit 1
		;;
	esac
}

main "$@"
