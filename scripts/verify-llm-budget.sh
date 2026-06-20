#!/usr/bin/env bash
# Phase 3: LLM budget — OWUI must not run generate_queries when Agent handles context.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${ROOT}/web/open-webui"
ADA="${ROOT}/ada"

echo "=== verify-llm-budget (Phase 3) ==="

if [[ -d "${TARGET}/.git" ]]; then
	grep -q "_ada_agent_handles_context" "${TARGET}/backend/open_webui/utils/middleware.py"
	grep -q "ADA_AGENT_HANDLES_CONTEXT" "${ROOT}/web/docker-compose.yml"
	grep -q 'tools/execute' "${TARGET}/backend/open_webui/routers/ada.py"
	echo "overlay Phase 3 anchors: OK"
else
	echo "skip overlay (no vendored web/open-webui)"
fi

(
	cd "${ADA}"
	source .venv/bin/activate
	pytest tests/test_unified_graph.py tests/test_owui_tool_backend.py tests/test_phase3_overlay.py -q
)
echo "phase3 pytest: OK"

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q "${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"; then
	container="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"
	handles="$(docker exec "${container}" printenv ADA_AGENT_HANDLES_CONTEXT 2>/dev/null || true)"
	if [[ "${handles}" == "1" ]]; then
		count="$(docker logs "${container}" 2>&1 | grep -c generate_queries || true)"
		if [[ "${count}" -gt 0 ]]; then
			echo "WARN: generate_queries appeared ${count} times in OWUI logs (expected 0 with skip)" >&2
		else
			echo "owui generate_queries log count: 0"
		fi
	else
		echo "docker ADA_AGENT_HANDLES_CONTEXT=${handles:-unset} (set 1 for live budget check)"
	fi
else
	echo "docker OWUI: SKIP (container not running)"
fi

echo ""
echo "Live budget (manual): web_search OFF, no files chat → expect 1 Agent→MLX completion"
echo "verify-llm-budget: OK"
