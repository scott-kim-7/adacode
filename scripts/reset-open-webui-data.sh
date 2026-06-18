#!/usr/bin/env bash
# Remove Open WebUI Docker volume (webui.db + uploads). Use after switching
# from ghcr.io/open-webui/open-webui:main to local v0.6.42 build.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/web/docker-compose.yml"
CONTAINER_NAME="${ADA_OPEN_WEBUI_CONTAINER:-adacode-open-webui}"

if ! docker info >/dev/null 2>&1; then
	echo "Docker is not running." >&2
	exit 1
fi

echo "Stopping Open WebUI and removing compose volume ..."
echo "  (accounts, chats, and settings in webui.db will be deleted)"
docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
docker rm -f "$CONTAINER_NAME" open-webui 2>/dev/null || true

# Legacy volume name from pre-compose or manual docker run
for legacy in open-webui web_open-webui; do
	if docker volume inspect "$legacy" >/dev/null 2>&1; then
		echo "Removing legacy volume: ${legacy}"
		docker volume rm "$legacy" 2>/dev/null || true
	fi
done

echo "Done. Start again with: ./scripts/ada.sh start"
