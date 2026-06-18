#!/usr/bin/env bash
# Start Ada LangGraph agent API (8082) if MLX (8080) is up.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

MLX_HOST="${ADA_MLX_HOST:-127.0.0.1}"
MLX_PORT="${ADA_MLX_PORT:-8080}"
AGENT_PORT="${ADA_AGENT_PORT:-8082}"
WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
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
	ada_mlx_up
}

agent_up() {
	curl -sf "http://${MLX_HOST}:${AGENT_PORT}/health" >/dev/null 2>&1
}

agent_models_ok() {
	curl -sf "http://${MLX_HOST}:${AGENT_PORT}/v1/models" >/dev/null 2>&1
}

# Optional full chat smoke (slow on large MLX models). Default off on --force restart.
agent_chat_ok() {
	local model out timeout
	timeout="${ADA_AGENT_SMOKE_TIMEOUT:-90}"
	if ! model="$(ada_resolve_openai_model "http://${MLX_HOST}:${AGENT_PORT}/v1" 2>/dev/null)"; then
		echo "  (no loaded model yet — agent up, pick a model in the UI to warm MLX)"
		return 0
	fi
	echo "  Chat smoke test (${model}, up to ${timeout}s) ..."
	# Buffered JSON only — SSE stream smoke can block for minutes on 30B+ models.
	out="$(curl -s -m "${timeout}" "http://${MLX_HOST}:${AGENT_PORT}/v1/chat/completions" \
		-H "Authorization: Bearer local" \
		-H "Content-Type: application/json" \
		-d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":8,\"stream\":false}" \
		2>/dev/null || true)"
	if [[ "$out" == *'"content"'* ]] || [[ "$out" == *'"finish_reason"'* ]]; then
		return 0
	fi
	return 1
}

agent_ready_ok() {
	agent_up && agent_models_ok
}

stop_agent() {
	if [[ -f "$PID_FILE" ]]; then
		ppid="$(cat "$PID_FILE" 2>/dev/null || true)"
		[[ -n "$ppid" ]] && kill "$ppid" 2>/dev/null || true
		rm -f "$PID_FILE"
	fi
	pkill -f "$SERVER_SCRIPT" 2>/dev/null || true
}

if ! ada_mlx_up; then
	echo "WARNING: MLX not running at http://${MLX_HOST}:${MLX_PORT} — starting agent anyway" >&2
fi

if [[ "$FORCE" -eq 0 ]] && agent_ready_ok; then
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
export PYTHONPATH="$ROOT/ada/src${PYTHONPATH:+:$PYTHONPATH}"
pip install -q httpx "fastapi>=0.115" "uvicorn>=0.32"

# Agent env (secrets passed only to the python process, then unset in this shell).
_agent_env=(
	"MLX_UPSTREAM=http://${MLX_HOST}:${MLX_PORT}"
	"ADA_AGENT_HOST=${MLX_HOST}"
	"ADA_AGENT_PORT=${AGENT_PORT}"
	"ADA_MODEL_REGISTRY=${ADA_MODEL_REGISTRY:-$ROOT/ada/config/model_registry.yaml}"
	"ADA_AGENT_FORCE_NON_STREAM=${ADA_AGENT_FORCE_NON_STREAM:-0}"
	"PYTHONPATH=$ROOT/ada/src${PYTHONPATH:+:$PYTHONPATH}"
)
[[ -n "${ADA_VAULT_UNLOCK_FD:-}" ]] && _agent_env+=("ADA_VAULT_UNLOCK_FD=${ADA_VAULT_UNLOCK_FD}")
_agent_env+=("ADA_CORS_ORIGINS=http://localhost:${WEBUI_PORT},http://127.0.0.1:${WEBUI_PORT}")

nohup env "${_agent_env[@]}" python "$SERVER_SCRIPT" >>"$LOG" 2>&1 &
unset _agent_env ADA_VAULT_UNLOCK_FD
echo $! >"$PID_FILE"
echo "  Waiting for agent /health ..."

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

if [[ "$FORCE" -eq 1 ]] && [[ "${ADA_AGENT_CHAT_SMOKE:-0}" != "1" ]]; then
	if agent_ready_ok; then
		echo "  Agent health + /v1/models OK (skipped chat smoke; set ADA_AGENT_CHAT_SMOKE=1 to run)"
	elif ada_mlx_up; then
		echo "WARNING: Agent up but /v1/models failed — check MLX and agent log" >&2
	fi
elif ! agent_chat_ok; then
	if ada_mlx_up; then
		echo "Agent chat test failed. Log:" >&2
		tail -20 "$LOG" >&2
		exit 1
	fi
	echo "Agent started (MLX not up — chat works once mlx_vlm.server is running)"
fi

echo "Ada agent server ready at http://${MLX_HOST}:${AGENT_PORT}/v1"
if [[ "${ADA_AGENT_FORCE_NON_STREAM:-0}" == "0" ]]; then
	echo "  streaming: SSE enabled (plan thinking + respond tokens)"
else
	echo "  streaming: buffered JSON (set ADA_AGENT_FORCE_NON_STREAM=0 for live tokens)"
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
	if docker ps --format '{{.Names}}' | grep -qx "${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"; then
		ada_sync_model_on_restart || true
	fi
fi
