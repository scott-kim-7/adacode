#!/usr/bin/env bash
# Diagnose Open WebUI + MLX setup (read-only checks).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=ada/mlx_defaults.sh
source "$ROOT/scripts/ada/mlx_defaults.sh"

HOST="${ADA_MLX_HOST:-127.0.0.1}"
PORT="${ADA_MLX_PORT:-8080}"
WEBUI_PORT="${ADA_OPEN_WEBUI_PORT:-3000}"
CONTAINER="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"

ok() { echo "  OK: $*"; }
fail() { echo "  FAIL: $*" >&2; }

echo "=== Ada chat diagnostics ==="
echo ""

echo "[1] Docker"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
	ok "Docker daemon running"
else
	fail "Docker Desktop not running — start it first"
fi

echo ""
echo "[2] MLX (http://${HOST}:${PORT})"
if curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1; then
	ok "MLX responding at http://${HOST}:${PORT}/v1"
else
	fail "MLX not running — run: ./scripts/serve-qwen.sh (keep terminal open)"
fi

echo ""
echo "[3] Port ${WEBUI_PORT}"
if lsof -iTCP:"${WEBUI_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
	docker ps --format '  container {{.Names}} — {{.Status}} — {{.Ports}}' --filter "publish=${WEBUI_PORT}" 2>/dev/null || true
else
	fail "Nothing listening on :${WEBUI_PORT} — run: ./scripts/serve-open-webui.sh"
fi

echo ""
echo "[4] Containers"
docker ps -a --format '  {{.Names}} — {{.Status}} — {{.Ports}}' 2>/dev/null | grep -iE 'webui|open-webui|adacode' || echo "  (no webui containers)"

if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
	echo ""
	echo "[5] MLX from inside ${CONTAINER}"
	if docker exec "$CONTAINER" curl -sf --connect-timeout 5 "http://host.docker.internal:${PORT}/v1/models" >/dev/null 2>&1; then
		ok "Container can reach MLX"
	else
		fail "Container cannot reach MLX — chat errors expected until MLX is up"
	fi
fi

echo ""
echo "Fix (typical order):"
echo "  1. ./scripts/serve-qwen.sh          # terminal 1, leave running"
echo "  2. docker rm -f open-webui adacode-open-webui 2>/dev/null; true"
echo "  3. ./scripts/serve-open-webui.sh    # terminal 2"
echo "  4. http://127.0.0.1:${WEBUI_PORT}"
