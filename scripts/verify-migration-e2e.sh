#!/usr/bin/env bash
# Phase 2–3 E2E closure: stack health + verify-phase2-owui + verify-llm-budget.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== verify-migration-e2e ==="
"${ROOT}/scripts/verify-phase2-owui.sh"
"${ROOT}/scripts/verify-llm-budget.sh"

AGENT_PORT="${ADA_AGENT_PORT:-9082}"
OWUI_PORT="${OWUI_PORT:-3000}"
STACK_AGENT=0
STACK_OWUI=0

if curl -sf --max-time 5 "http://127.0.0.1:${AGENT_PORT}/health" >/dev/null; then
	STACK_AGENT=1
	echo "task title smoke..."
	code="$(curl -s -o /tmp/ada-task-title.json -w '%{http_code}' \
		-X POST "http://127.0.0.1:${AGENT_PORT}/v1/chat/completions" \
		-H "Content-Type: application/json" \
		-H "X-Ada-Request-Kind: task" \
		-d '{"model":"mlx-coder","messages":[{"role":"user","content":"hi"}],"metadata":{"task":"title_generation","task_body":{"messages":[{"role":"user","content":"hello"}]}}}')"
	if [[ "${code}" == "200" ]]; then
		echo "task title API: OK (HTTP 200)"
	else
		echo "task title API: FAIL (HTTP ${code})" >&2
		cat /tmp/ada-task-title.json >&2 || true
		exit 1
	fi
else
	echo "agent health: SKIP (run ./scripts/ada.sh start from a TTY for vault unlock)"
fi

if curl -sf --max-time 5 "http://127.0.0.1:${OWUI_PORT}/health" >/dev/null; then
	STACK_OWUI=1
else
	echo "owui health: SKIP (Docker + ./scripts/ada.sh start)"
fi

if [[ "${ADA_REQUIRE_STACK:-0}" == "1" ]]; then
	if [[ "${STACK_AGENT}" -eq 0 || "${STACK_OWUI}" -eq 0 ]]; then
		echo "ADA_REQUIRE_STACK=1 but stack incomplete (agent=${STACK_AGENT} owui=${STACK_OWUI})" >&2
		exit 1
	fi
fi

echo "verify-migration-e2e: OK (automated; live stack agent=${STACK_AGENT} owui=${STACK_OWUI})"
