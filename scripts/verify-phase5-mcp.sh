#!/usr/bin/env bash
# Phase 5: overlay MCP tool execute + middleware agent tool skip.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${ROOT}/web/open-webui"
ADA="${ROOT}/ada"

echo "=== verify-phase5-mcp ==="
if [[ -d "${TARGET}/.git" ]]; then
	grep -q '_resolve_tools_dict' "${TARGET}/backend/open_webui/routers/ada.py"
	grep -q 'tool_calls.clear()' "${TARGET}/backend/open_webui/utils/middleware.py"
	! grep -q 'server:mcp:' "${TARGET}/backend/open_webui/utils/middleware.py" || \
		! grep -A6 'tool_calls.clear()' "${TARGET}/backend/open_webui/utils/middleware.py" | grep -q 'server:mcp:' || \
		echo "WARN: middleware may still exclude MCP from tool skip"
	echo "overlay Phase 5 anchors: OK"
else
	echo "skip overlay (no vendored web/open-webui)"
fi

(
	cd "${ADA}"
	source .venv/bin/activate
	pytest tests/test_tool_policy.py tests/test_owui_tool_backend.py -q
)
echo "phase5 pytest: OK"
echo "verify-phase5-mcp: OK"
