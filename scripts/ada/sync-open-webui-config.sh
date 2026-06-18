#!/usr/bin/env bash
# Sync Open WebUI SQLite config with Ada Agent URL + loaded MLX model.
set -euo pipefail

_SYNC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${_SYNC_DIR}/../.." && pwd)"
if ! declare -F ada_mlx_host >/dev/null 2>&1; then
	# shellcheck source=ada/mlx_defaults.sh
	source "$ROOT/scripts/ada/mlx_defaults.sh"
fi

CONTAINER="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"
AGENT_PORT="${ADA_AGENT_PORT:-9082}"
WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
SCRIPT="$ROOT/scripts/ada/sync_openwebui_config.py"

agent_openai_base() {
	local base="http://host.docker.internal:${AGENT_PORT}/v1"
	if [[ "$(uname -s)" == "Linux" ]]; then
		local host
		host="$(ada_mlx_host)"
		base="http://${host}:${AGENT_PORT}/v1"
		if [[ "$host" == "127.0.0.1" || "$host" == "localhost" ]]; then
			base="http://172.17.0.1:${AGENT_PORT}/v1"
		fi
	fi
	echo "$base"
}

ada_sync_openwebui_config() {
	local agent_url model_id restart="${1:-1}"
	agent_url="$(agent_openai_base)"
	model_id="$(ada_default_model_id || true)"

	if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
		echo "Open WebUI container ${CONTAINER} is not running." >&2
		return 1
	fi

	echo "Syncing Open WebUI DB → Agent ${agent_url}"
	local -a py_args=(--agent-url "$agent_url" --api-key local)
	if [[ -n "$model_id" ]]; then
		py_args+=(--model-id "$model_id" --pinned-model-id "$model_id")
		echo "  default model: ${model_id}"
	fi

	docker cp "$SCRIPT" "${CONTAINER}:/tmp/sync_openwebui_config.py" >/dev/null
	local sync_out
	sync_out="$(docker exec "$CONTAINER" python3 /tmp/sync_openwebui_config.py "${py_args[@]}")"
	echo "$sync_out"
	echo "$sync_out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
b, a = d.get('before_models'), d.get('after_models')
if b and a and b != a:
    print(f'  updated default_models: {b!r} → {a!r}')
elif a:
    print(f'  default_models: {a!r}')
" 2>/dev/null || true

	if [[ "$restart" == "1" ]]; then
		echo "Restarting ${CONTAINER} to reload persisted config ..."
		docker restart "$CONTAINER" >/dev/null
		for ((i = 1; i <= 60; i++)); do
			if curl -sf "http://127.0.0.1:${WEBUI_PORT}/" >/dev/null 2>&1; then
				break
			fi
			sleep 2
			if [[ $i -eq 60 ]]; then
				echo "Open WebUI did not become ready after restart." >&2
				return 1
			fi
		done
	fi

	if docker exec "$CONTAINER" \
		curl -sf --connect-timeout 5 "${agent_url}/models" >/dev/null 2>&1; then
		echo "Open WebUI → Agent model list: OK"
	else
		echo "WARNING: container cannot reach ${agent_url}/models" >&2
		return 1
	fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	ada_sync_openwebui_config "${1:-1}"
fi
