#!/usr/bin/env bash
# Ada web-only smoke tests: Python package + docker compose config.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADA="$ROOT/ada"
VENV="$ADA/.venv"
COMPOSE_FILE="$ROOT/web/docker-compose.yml"

echo "=== Ada verify (web-only) ==="

if [[ ! -d "$VENV" ]]; then
	python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -e "$ADA[dev]"

echo ""
echo "[1/4] Regression tests"
pytest "$ADA/tests/regression/" -m regression -q

echo ""
echo "[2/4] Full Python tests"
pytest "$ADA/tests/" -q

echo ""
echo "[3/4] Package import"
python -c "from ada.agent import AgentSession; from ada.registry import load_registry; print('ada OK')"

echo ""
echo "[4/4] Open WebUI compose"
if command -v docker >/dev/null 2>&1; then
	docker compose -f "$COMPOSE_FILE" config >/dev/null
	echo "docker compose OK"
else
	echo "docker not installed — skip compose check"
fi

# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"
HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
if curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1; then
	echo "MLX server reachable at http://${HOST}:${PORT}"
else
	echo "MLX not running (optional): ./scripts/serve-qwen.sh"
fi

WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
if curl -sf "http://127.0.0.1:${WEBUI_PORT}" >/dev/null 2>&1; then
	echo "Open WebUI reachable at http://127.0.0.1:${WEBUI_PORT}"
else
	echo "Open WebUI not running (optional): ./scripts/serve-ada.sh"
fi

echo ""
echo "Ada verify passed."
echo "Quick start: ./scripts/serve-qwen.sh && ./scripts/serve-ada.sh"
