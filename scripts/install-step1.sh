#!/usr/bin/env bash
# Step 1 one-shot setup: BYOK chatLanguageModels.json + settings.json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_DIR="$("$ROOT/scripts/resolve-vscode-user-dir.sh")"
MODELS_SOURCE="$ROOT/docs/ada/step1/chatLanguageModels.example.json"
MODELS_TARGET="$USER_DIR/chatLanguageModels.json"
SETTINGS_TARGET="$USER_DIR/settings.json"
SETTINGS_SNIPPET="$ROOT/docs/ada/step1/settings.example.json"

if [[ ! -f "$MODELS_SOURCE" ]]; then
	echo "Missing $MODELS_SOURCE" >&2
	exit 1
fi

mkdir -p "$USER_DIR"

if [[ -f "$MODELS_TARGET" ]]; then
	BACKUP="${MODELS_TARGET}.bak.$(date +%Y%m%d-%H%M%S)"
	cp "$MODELS_TARGET" "$BACKUP"
	echo "Backed up chatLanguageModels.json → $BACKUP"
fi
cp "$MODELS_SOURCE" "$MODELS_TARGET"
echo "Installed $MODELS_TARGET"

python3 "$ROOT/scripts/ada/install_step1_settings.py" "$SETTINGS_TARGET" "$SETTINGS_SNIPPET"

echo ""
echo "Step 1 setup complete."
echo "Run: ./scripts/adacode.sh"
