#!/usr/bin/env bash
# Ada web stack: stop / start / restart MLX + proxy + Open WebUI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_MLX_HOST:-127.0.0.1}"
MLX_PORT="${ADA_MLX_PORT:-8080}"
PROXY_PORT="${ADA_MLX_PROXY_PORT:-8081}"
WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
CONTAINER="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"
COMPOSE_FILE="$ROOT/web/docker-compose.yml"
MODEL="${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}"
MLX_LOG="${ADA_MLX_LOG:-$ROOT/.ada-mlx-server.log}"
MLX_PID_FILE="${ADA_MLX_PID_FILE:-$ROOT/.ada-mlx-server.pid}"
DAEMON_PID_FILE="${ADA_MLX_DAEMON_PID:-$ROOT/.ada-mlx-daemon.pid}"
PROXY_PID_FILE="${ADA_MLX_PROXY_PID:-$ROOT/.ada-mlx-proxy.pid}"
PROXY_SCRIPT="$ROOT/scripts/mlx_openai_proxy.py"

usage() {
	cat <<EOF
Usage: $(basename "$0") [command]

Commands:
  restart   Stop everything, then start fresh (default)
  start     Start MLX, compatibility proxy, and Open WebUI
  stop      Stop Open WebUI, proxy, and MLX
  status    Show whether each service is up

Environment (optional):
  ADA_MLX_MODEL              MLX model id (default: $ADA_MLX_MODEL_DEFAULT)
  ADA_MLX_PORT               MLX OpenAI API port (default: 8080)
  ADA_MLX_PROXY_PORT         Open WebUI proxy port (default: 8081)
  ADA_OPEN_WEBUI_PORT        Browser UI port (default: 3000)

Examples:
  ./scripts/ada.sh
  ./scripts/ada.sh stop
  ./scripts/ada.sh start
  ADA_MLX_MODEL=mlx-community/Qwen3-VL-32B-Instruct-8bit ./scripts/ada.sh restart
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
	echo "[1/3] Open WebUI"
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

stop_proxy() {
	echo "[2/3] MLX OpenAI proxy"
	kill_pid_file "$PROXY_PID_FILE" "MLX proxy"
	pkill -f "$PROXY_SCRIPT" 2>/dev/null || true
	kill_port_listeners "$PROXY_PORT" "MLX proxy"
	sleep 1
	if curl -sf "http://${HOST}:${PROXY_PORT}/v1/models" >/dev/null 2>&1; then
		echo "  WARNING: proxy still responds on :${PROXY_PORT}" >&2
	else
		echo "  stopped (:${PROXY_PORT} free)"
	fi
}

stop_mlx() {
	echo "[3/3] MLX server"
	kill_pid_file "$DAEMON_PID_FILE" "MLX daemon"
	"$ROOT/scripts/stop-mlx-server.sh" || true
	pkill -f "mlx_vlm.server" 2>/dev/null || true
	pkill -f "mlx_lm.server" 2>/dev/null || true
	kill_port_listeners "$MLX_PORT" "MLX server"
	sleep 1
	if curl -sf "http://${HOST}:${MLX_PORT}/v1/models" >/dev/null 2>&1; then
		echo "  WARNING: MLX still responds on :${MLX_PORT}" >&2
	else
		echo "  stopped (:${MLX_PORT} free)"
	fi
}

stop_all() {
	echo "=== Stop Ada stack ==="
	stop_webui
	stop_proxy
	stop_mlx
	echo ""
	echo "All Ada services stopped."
}

mlx_up() {
	curl -sf "http://${HOST}:${MLX_PORT}/v1/models" >/dev/null 2>&1
}

proxy_up() {
	curl -sf "http://${HOST}:${PROXY_PORT}/v1/models" >/dev/null 2>&1
}

webui_up() {
	curl -sf "http://127.0.0.1:${WEBUI_PORT}/" >/dev/null 2>&1
}

start_mlx() {
	echo "[1/3] MLX server ($MODEL)"
	nohup env ADA_MLX_MODEL="$MODEL" "$ROOT/scripts/serve-qwen.sh" >>"$MLX_LOG" 2>&1 &
	echo $! >"$MLX_PID_FILE"
	echo "  pid: $(cat "$MLX_PID_FILE")"
	echo "  log: $MLX_LOG"
	echo -n "  waiting"
	for i in $(seq 1 90); do
		if mlx_up; then
			echo " ready"
			return 0
		fi
		echo -n "."
		sleep 2
	done
	echo " FAILED" >&2
	tail -20 "$MLX_LOG" >&2
	return 1
}

start_proxy() {
	echo "[2/3] MLX OpenAI proxy (:${PROXY_PORT})"
	export ADA_MLX_MODEL="$MODEL"
	"$ROOT/scripts/ensure-mlx-proxy.sh" --force
}

start_webui() {
	echo "[3/3] Open WebUI (:${WEBUI_PORT})"
	export ADA_MLX_MODEL="$MODEL"
	export ADA_MLX_HOST="$HOST"
	export ADA_MLX_PORT="$MLX_PORT"
	export ADA_OPEN_WEBUI_PORT="$WEBUI_PORT"
	export ADA_OPEN_WEBUI_CONTAINER="$CONTAINER"
	"$ROOT/scripts/serve-open-webui.sh"
}

start_all() {
	echo "=== Start Ada stack ==="
	if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
		echo "Docker Desktop is not running. Start it, then retry." >&2
		exit 1
	fi
	start_mlx
	start_proxy
	start_webui
	echo ""
	echo "Ada stack is running."
	echo "  MLX:    http://${HOST}:${MLX_PORT}/v1"
	echo "  Proxy:  http://${HOST}:${PROXY_PORT}/v1"
	echo "  UI:     http://127.0.0.1:${WEBUI_PORT}"
	echo "  Model:  ${MODEL}"
	echo ""
	echo "Open a NEW chat in the browser and pick: ${MODEL}"
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
	local mlx_ok=0 proxy_ok=0 webui_ok=0 docker_ok=0
	mlx_up && mlx_ok=1
	proxy_up && proxy_ok=1
	webui_up && webui_ok=1
	if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
		docker_ok=1
	fi
	status_line "MLX :${MLX_PORT}" "$mlx_ok" "$MODEL"
	status_line "Proxy :${PROXY_PORT}" "$proxy_ok" "Open WebUI → MLX"
	status_line "WebUI :${WEBUI_PORT}" "$webui_ok" "http://127.0.0.1:${WEBUI_PORT}"
	status_line "Docker ${CONTAINER}" "$docker_ok" "$(docker ps --filter "name=${CONTAINER}" --format '{{.Status}}' 2>/dev/null || echo 'not running')"
	echo ""
	if [[ "$mlx_ok$proxy_ok$webui_ok" == "111" ]]; then
		echo "Ready. Use a NEW chat after restart."
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
