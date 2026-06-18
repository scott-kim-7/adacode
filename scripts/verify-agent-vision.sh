#!/usr/bin/env bash
# Smoke test: LangGraph agent API (:9082) accepts multimodal chat.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_AGENT_HOST:-127.0.0.1}"
AGENT_PORT="${ADA_AGENT_PORT:-9082}"
MLX_PORT="${ADA_MLX_PORT:-8080}"

echo "=== Verify agent vision (:${AGENT_PORT}) ==="

if ! curl -sf "http://${HOST}:${MLX_PORT}/v1/models" >/dev/null 2>&1; then
	echo "MLX not running on :${MLX_PORT}. Start: ./scripts/ada.sh start" >&2
	exit 1
fi

if ! curl -sf "http://${HOST}:${AGENT_PORT}/v1/models" >/dev/null 2>&1; then
	echo "Agent not running on :${AGENT_PORT}. Start: ./scripts/ensure-ada-agent-server.sh" >&2
	exit 1
fi

python3 "$ROOT/scripts/ada/verify_agent_vision.py"
