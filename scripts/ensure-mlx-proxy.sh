#!/usr/bin/env bash
# Start mlx-openai-proxy (9081) if MLX (8080) is up.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

MLX_HOST="${ADA_MLX_HOST:-127.0.0.1}"
MLX_PORT="${ADA_MLX_PORT:-8080}"
PROXY_PORT="${ADA_MLX_PROXY_PORT:-9081}"
PID_FILE="${ADA_MLX_PROXY_PID:-$ROOT/.ada-mlx-proxy.pid}"
LOG="${ADA_MLX_PROXY_LOG:-$ROOT/.ada-mlx-proxy.log}"
VENV="$ROOT/ada/.venv"
PROXY_SCRIPT="$ROOT/scripts/mlx_openai_proxy.py"
FORCE=0

usage() {
	echo "Usage: $0 [--force|-f]" >&2
	echo "  Start Open WebUI compatibility proxy on :${PROXY_PORT}" >&2
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

proxy_up() {
	curl -sf "http://${MLX_HOST}:${PROXY_PORT}/v1/models" >/dev/null 2>&1
}

proxy_stream_ok() {
	local model out
	model="$(curl -sf "http://${MLX_HOST}:${MLX_PORT}/v1/models" | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])")"
	out="$(curl -s -N -m 120 "http://${MLX_HOST}:${PROXY_PORT}/v1/chat/completions" \
		-H "Authorization: Bearer local" \
		-H "Content-Type: application/json" \
		-d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":8,\"stream\":true}" \
		2>/dev/null || true)"
	# Buffered mode returns JSON even when stream=true was requested.
	if [[ "$out" == *'"message"'* && "$out" == *'"content"'* ]]; then
		return 0
	fi
	[[ "$out" == *'"content"'* ]]
}

stop_proxy() {
	if [[ -f "$PID_FILE" ]]; then
		ppid="$(cat "$PID_FILE" 2>/dev/null || true)"
		[[ -n "$ppid" ]] && kill "$ppid" 2>/dev/null || true
		rm -f "$PID_FILE"
	fi
	pkill -f "$PROXY_SCRIPT" 2>/dev/null || true
}

if ! mlx_up; then
	echo "MLX not running at http://${MLX_HOST}:${MLX_PORT}" >&2
	echo "Start the LLM server on port ${MLX_PORT} before continuing." >&2
	exit 1
fi

if [[ "$FORCE" -eq 0 ]] && proxy_up && proxy_stream_ok; then
	echo "MLX proxy already running at http://${MLX_HOST}:${PROXY_PORT}/v1"
	exit 0
fi

if [[ "$FORCE" -eq 0 ]] && proxy_up; then
	echo "MLX proxy responds but streaming looks broken — restarting ..."
fi

stop_proxy
sleep 1

if [[ ! -d "$VENV" ]]; then
	"$ROOT/scripts/install-step2.sh"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q httpx "fastapi>=0.115" "uvicorn>=0.32"

export MLX_UPSTREAM="http://${MLX_HOST}:${MLX_PORT}"
export ADA_MLX_PROXY_HOST="$MLX_HOST"
export ADA_MLX_PROXY_PORT="$PROXY_PORT"

nohup python "$PROXY_SCRIPT" >>"$LOG" 2>&1 &
echo $! >"$PID_FILE"

for i in $(seq 1 30); do
	if proxy_up; then
		break
	fi
	sleep 1
	if [[ $i -eq 30 ]]; then
		echo "Proxy failed to start. Log:" >&2
		tail -20 "$LOG" >&2
		exit 1
	fi
done

if ! proxy_stream_ok; then
	echo "Proxy stream test failed. Log:" >&2
	tail -20 "$LOG" >&2
	exit 1
fi

echo "MLX proxy ready at http://${MLX_HOST}:${PROXY_PORT}/v1"
