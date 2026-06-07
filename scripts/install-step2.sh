#!/usr/bin/env bash
# Install ada Python package (venv + editable install).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADA="$ROOT/ada"
VENV="$ADA/.venv"

if [[ ! -d "$VENV" ]]; then
	echo "Creating ada venv at $VENV ..."
	python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -U pip
pip install -q -e "$ADA[dev]"

echo ""
echo "Ada Python package installed."
echo "  venv: $VENV"
echo "  CLI:  ada profiles | ada tri-chat | ada ada-agent"
echo ""
echo "Web UI: ./scripts/serve-qwen.sh && ./scripts/serve-ada.sh"
