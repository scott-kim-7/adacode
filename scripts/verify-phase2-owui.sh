#!/usr/bin/env bash
# Phase 2 closure: overlay anchors, pytest, optional live stack + JWT retrieval.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${ROOT}/web/open-webui"
ADA="${ROOT}/ada"

echo "=== Phase 2 verify ==="

# --- overlay anchors (vendored tree) ---
if [[ -d "${TARGET}/.git" ]]; then
	grep -q "Ada Phase 2" "${TARGET}/backend/open_webui/utils/middleware.py"
	grep -q '"features"' "${TARGET}/backend/open_webui/routers/openai.py"
	grep -q 'retrieval/sources' "${TARGET}/backend/open_webui/routers/ada.py"
	grep -q 'X-Ada-Owui-Authorization' "${TARGET}/backend/open_webui/routers/openai.py"
	echo "overlay anchors: OK"
else
	echo "skip overlay anchors (no vendored web/open-webui)"
fi

# --- unit tests ---
(
	cd "${ADA}"
	source .venv/bin/activate
	pytest tests/test_web_search.py tests/test_unified_graph.py \
		tests/test_owui_retrieval_backend.py tests/test_owui_memory_backend.py \
		tests/test_task_graph.py -q
)
echo "phase2 pytest: OK"

# --- optional live stack ---
AGENT_PORT="${ADA_AGENT_PORT:-9082}"
OWUI_PORT="${OWUI_PORT:-3000}"
MLX_PORT="${ADA_MLX_PORT:-8089}"

check_url() {
	local url="$1"
	local label="$2"
	if curl -sf --max-time 3 "${url}" >/dev/null; then
		echo "${label}: OK (${url})"
		return 0
	fi
	echo "${label}: SKIP (unreachable ${url})"
	return 1
}

STACK_UP=0
check_url "http://127.0.0.1:${AGENT_PORT}/health" "agent health" && STACK_UP=1 || true
check_url "http://127.0.0.1:${OWUI_PORT}/health" "owui health" || true
check_url "http://127.0.0.1:${MLX_PORT}/v1/models" "mlx models" || true

if [[ -n "${OWUI_JWT:-}" ]]; then
	echo "JWT retrieval/sources smoke..."
	code="$(curl -s -o /tmp/ada-phase2-retrieval.json -w '%{http_code}' \
		-X POST "http://127.0.0.1:${OWUI_PORT}/api/v1/ada/retrieval/sources" \
		-H "Authorization: Bearer ${OWUI_JWT}" \
		-H "Content-Type: application/json" \
		-d '{"items":[],"queries":["test"],"full_context":false}')"
	if [[ "${code}" == "200" ]]; then
		echo "retrieval/sources: OK (HTTP 200)"
	else
		echo "retrieval/sources: FAIL (HTTP ${code})" >&2
		cat /tmp/ada-phase2-retrieval.json >&2 || true
		exit 1
	fi
else
	echo "retrieval/sources JWT: SKIP (set OWUI_JWT for live smoke)"
fi

if [[ "${STACK_UP}" -eq 1 ]]; then
	echo "agent unified chat smoke..."
	code="$(curl -s -o /tmp/ada-phase2-chat.json -w '%{http_code}' \
		-X POST "http://127.0.0.1:${AGENT_PORT}/v1/chat/completions" \
		-H "Content-Type: application/json" \
		-H 'X-OpenWebUI-Metadata: {"features":{"memory":false,"web_search":false}}' \
		-d '{"model":"mlx-coder","messages":[{"role":"user","content":"ping"}],"stream":false}')"
	if [[ "${code}" == "200" ]]; then
		echo "agent unified chat: OK (HTTP 200)"
	else
		echo "agent unified chat: FAIL (HTTP ${code})" >&2
		cat /tmp/ada-phase2-chat.json >&2 || true
		exit 1
	fi
	echo "live stack: partial OK (see above)"
else
	echo "live stack: SKIP (start with ./scripts/ada.sh start)"
fi

echo ""
echo "Manual E2E (not automated here):"
echo "  1. OWUI chat with web_search ON → Agent logs search_batch"
echo "  2. native tool chat → OWUI process_chat_response executes tool_calls (D14)"
echo ""
echo "Phase 2 verify passed."
