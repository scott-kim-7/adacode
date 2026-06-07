#!/usr/bin/env bash
# Start Ada LangGraph agent API (8082) if MLX (8080) is up.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

MLX_HOST="${ADA_MLX_HOST:-127.0.0.1}"
MLX_PORT="${ADA_MLX_PORT:-8080}"
AGENT_PORT="${ADA_AGENT_PORT:-8082}"
PID_FILE="${ADA_AGENT_PID:-$ROOT/.ada-agent-server.pid}"
LOG="${ADA_AGENT_LOG:-$ROOT/.ada-agent-server.log}"
VENV="$ROOT/ada/.venv"
SERVER_SCRIPT="$ROOT/scripts/ada_agent_server.py"
FORCE=0

usage() {
	echo "Usage: $0 [--force|-f]" >&2
	echo "  Start LangGraph OpenAI API on :${AGENT_PORT}" >&2
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	-f | --force)
		FORCE=1
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
	curl -sf "http://${MLX_HOST}:${MLX_PORT}/v1/models" >/dev/null 2>&1
}

agent_up() {
	curl -sf "http://${MLX_HOST}:${AGENT_PORT}/v1/models" >/dev/null 2>&1
}

agent_chat_ok() {
	local out
	out="$(curl -s -m 180 "http://${MLX_HOST}:${AGENT_PORT}/v1/chat/completions" \
		-H "Authorization: Bearer local" \
		-H "Content-Type: application/json" \
		-d "{\"model\":\"${ADA_MLX_MODEL:-$ADA_MLX_MODEL_DEFAULT}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":16,\"stream\":true}" \
		2>/dev/null || true)"
	[[ "$out" == *'"message"'* && "$out" == *'"content"'* ]]
}

stop_agent() {
	if [[ -f "$PID_FILE" ]]; then
		ppid="$(cat "$PID_FILE" 2>/dev/null || true)"
		[[ -n "$ppid" ]] && kill "$ppid" 2>/dev/null || true
		rm -f "$PID_FILE"
	fi
	pkill -f "$SERVER_SCRIPT" 2>/dev/null || true
}

if ! mlx_up; then
	echo "MLX not running at http://${MLX_HOST}:${MLX_PORT}" >&2
	echo "Start: ./scripts/restart-mlx.sh" >&2
	exit 1
fi

if [[ "$FORCE" -eq 0 ]] && agent_up && agent_chat_ok; then
	echo "Ada agent server already running at http://${MLX_HOST}:${AGENT_PORT}/v1"
	exit 0
fi

if [[ "$FORCE" -eq 0 ]] && agent_up; then
	echo "Agent server responds but chat test failed — restarting ..."
fi

stop_agent
sleep 1

if [[ ! -d "$VENV" ]]; then
	"$ROOT/scripts/install-step2.sh"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q httpx "fastapi>=0.115" "uvicorn>=0.32"

export MLX_UPSTREAM="http://${MLX_HOST}:${MLX_PORT}"
export ADA_AGENT_HOST="$MLX_HOST"
export ADA_AGENT_PORT="$AGENT_PORT"
export ADA_MODEL_REGISTRY="${ADA_MODEL_REGISTRY:-$ROOT/ada/config/model_registry.yaml}"

nohup python "$SERVER_SCRIPT" >>"$LOG" 2>&1 &
echo $! >"$PID_FILE"

for i in $(seq 1 30); do
	if agent_up; then
		break
	fi
	sleep 1
	if [[ $i -eq 30 ]]; then
		echo "Agent server failed to start. Log:" >&2
		tail -20 "$LOG" >&2
		exit 1
	fi
done

if ! agent_chat_ok; then
	echo "Agent chat test failed. Log:" >&2
	tail -20 "$LOG" >&2
	exit 1
fi

echo "Ada agent server ready at http://${MLX_HOST}:${AGENT_PORT}/v1"
