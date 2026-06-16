# Shared MLX / OpenAPI defaults (source from bash scripts).

ada_mlx_host() {
	echo "${ADA_MLX_HOST:-127.0.0.1}"
}

ada_mlx_port() {
	echo "${ADA_MLX_PORT:-8080}"
}

ada_mlx_url() {
	echo "http://$(ada_mlx_host):$(ada_mlx_port)"
}

# True if mlx_lm / mlx-vlm responds on /health or /v1/models.
ada_mlx_curl_ok() {
	local url="$1"
	curl -sf --connect-timeout 3 -H "Authorization: Bearer local" "$url" >/dev/null 2>&1 \
		|| curl -sf --connect-timeout 3 "$url" >/dev/null 2>&1
}

ada_mlx_up() {
	local base
	base="$(ada_mlx_url)"
	ada_mlx_curl_ok "${base}/health" && return 0
	ada_mlx_curl_ok "${base}/v1/models" && return 0
	return 1
}

# Wait up to ADA_MLX_WAIT_SEC (default 30) for the LLM server.
ada_wait_mlx_up() {
	local max="${ADA_MLX_WAIT_SEC:-30}"
	local i
	for ((i = 1; i <= max; i++)); do
		if ada_mlx_up; then
			return 0
		fi
		if [[ "$i" -lt "$max" ]]; then
			sleep 1
		fi
	done
	return 1
}

# Warn if MLX is down but do not block Ada Agent / WebUI (MLX is external).
ada_warn_mlx_up() {
	if ada_mlx_up; then
		return 0
	fi
	local base
	base="$(ada_mlx_url)"
	echo "WARNING: LLM server is not reachable at ${base}" >&2
	echo "  checked: ${base}/health and ${base}/v1/models" >&2
	echo "Ada will start Agent + WebUI anyway. Start mlx_vlm when ready:" >&2
	echo "  python -m mlx_vlm.server --host $(ada_mlx_host) --port $(ada_mlx_port)" >&2
	return 1
}

# Exit 1 if the LLM server is not listening (for scripts that only make sense with MLX).
ada_require_mlx_up() {
	if ada_wait_mlx_up; then
		return 0
	fi
	ada_warn_mlx_up
	exit 1
}

# Model id for Open WebUI (mlx /health loaded_model, else Agent GET /v1/models).
ada_default_model_id() {
	local host agent_port
	host="$(ada_mlx_host)"
	agent_port="${ADA_AGENT_PORT:-8082}"
	if ada_mlx_curl_ok "$(ada_mlx_url)/health"; then
		local loaded
		loaded="$(curl -sf "$(ada_mlx_url)/health" | python3 -c "import json,sys; print(json.load(sys.stdin).get('loaded_model') or '')" 2>/dev/null || true)"
		if [[ -n "$loaded" ]]; then
			echo "$loaded"
			return 0
		fi
	fi
	if curl -sf "http://${host}:${agent_port}/v1/models" >/dev/null 2>&1; then
		curl -sf "http://${host}:${agent_port}/v1/models" | python3 -c "
import json, sys
data = json.load(sys.stdin).get('data') or []
print(data[0]['id'] if data else '', end='')
" 2>/dev/null || true
	fi
}

# Export DEFAULT_MODELS for Open WebUI docker-compose (from mlx_vlm --model / loaded_model).
ada_export_webui_model_env() {
	local model
	model="$(ada_default_model_id)"
	if [[ -n "$model" ]]; then
		export DEFAULT_MODELS="$model"
		export DEFAULT_PINNED_MODELS="$model"
	fi
}

ada_repo_root() {
	cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

# Current DEFAULT_MODELS inside a running Open WebUI container (empty if unset).
ada_webui_container_model_env() {
	local container="${1:-${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}}"
	if ! command -v docker >/dev/null 2>&1; then
		return 0
	fi
	docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$container" 2>/dev/null \
		| sed -n 's/^DEFAULT_MODELS=//p' | head -1
}

# Wait until Open WebUI responds on WEBUI_PORT.
ada_wait_webui_up() {
	local port="${1:-${ADA_OPEN_WEBUI_PORT:-3000}}"
	local max="${2:-60}"
	local i
	for ((i = 1; i <= max; i++)); do
		if curl -sf "http://127.0.0.1:${port}/" >/dev/null 2>&1; then
			return 0
		fi
		sleep 2
	done
	return 1
}

# Align Open WebUI env + SQLite with mlx_vlm GET /health loaded_model.
# Safe to call on every ./scripts/ada.sh restart|start and after agent-only restarts.
ada_sync_model_on_restart() {
	local root model container port compose agent_port
	root="$(ada_repo_root)"
	container="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"
	port="${ADA_OPEN_WEBUI_PORT:-3000}"
	agent_port="${ADA_AGENT_PORT:-8082}"
	compose="$root/web/docker-compose.yml"

	model="$(ada_default_model_id || true)"
	if [[ -z "$model" ]]; then
		echo "Model sync: skipped (MLX loaded_model not available yet)" >&2
		return 0
	fi

	ada_export_webui_model_env
	echo "Model sync: ${model} (from mlx_vlm /health loaded_model)"

	if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
		return 0
	fi
	if ! docker ps --format '{{.Names}}' | grep -qx "$container"; then
		return 0
	fi

	local current="${ADA_OPEN_WEBUI_CONTAINER_MODEL_ENV:-}"
	if [[ -z "$current" ]]; then
		current="$(ada_webui_container_model_env "$container" || true)"
	fi
	if [[ "$current" != "$model" ]]; then
		echo "Model sync: refreshing container env (was: ${current:-<unset>})"
		export ADA_OPEN_WEBUI_PORT="$port"
		export ADA_OPEN_WEBUI_CONTAINER="$container"
		export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-http://host.docker.internal:${agent_port}/v1}"
		if [[ "$(uname -s)" == "Linux" ]]; then
			export OPENAI_API_BASE_URL="http://$(ada_mlx_host):${agent_port}/v1"
			if [[ "$(ada_mlx_host)" == "127.0.0.1" || "$(ada_mlx_host)" == "localhost" ]]; then
				export OPENAI_API_BASE_URL="http://172.17.0.1:${agent_port}/v1"
			fi
		fi
		export OPENAI_API_KEY="${OPENAI_API_KEY:-local}"
		docker compose -f "$compose" up -d --force-recreate
		if ! ada_wait_webui_up "$port"; then
			echo "Model sync: Open WebUI did not become ready on :${port}" >&2
			return 1
		fi
	fi

	# DB-persisted defaults override compose env; patch every restart.
	# shellcheck source=ada/sync-open-webui-config.sh
	source "$root/scripts/ada/sync-open-webui-config.sh"
	ada_sync_openwebui_config 1
}

# Print loaded model id from GET /health (empty if none loaded yet).
ada_resolve_openai_model() {
	local base="${1:-$(ada_mlx_url)/v1}"
	local key="${2:-local}"
	local root
	root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
	PYTHONPATH="${root}/ada/src${PYTHONPATH:+:$PYTHONPATH}" python - <<PY
from ada.openai_models import resolve_model_id
print(resolve_model_id("${base}", api_key="${key}"))
PY
}
