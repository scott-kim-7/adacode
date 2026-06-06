#!/usr/bin/env bash
# Step 2: merge external LLM BYOK group into chatLanguageModels.json (keeps Local Qwen from Step 1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_DIR="$("$ROOT/scripts/resolve-vscode-user-dir.sh")"
TARGET="$USER_DIR/chatLanguageModels.json"
EXTERNAL="$ROOT/docs/ada/step2/chatLanguageModels.external.example.json"
STEP1="$ROOT/docs/ada/step1/chatLanguageModels.example.json"

mkdir -p "$USER_DIR"

python3 - "$TARGET" "$STEP1" "$EXTERNAL" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
step1 = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
external = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

if target.is_file():
	existing = json.loads(target.read_text(encoding="utf-8"))
else:
	existing = []

def vendor_key(entry: dict) -> tuple:
	return (entry.get("vendor"), entry.get("name"))

merged: dict[tuple, dict] = {}
for src in (existing, step1, external):
	for entry in src:
		merged[vendor_key(entry)] = entry

out = list(merged.values())
target.write_text(json.dumps(out, indent="\t") + "\n", encoding="utf-8")
print(f"Merged Step 1 + external BYOK → {target}")
PY

echo ""
echo "Step 2 BYOK merge complete."
echo "Replace External OpenAI apiKey or use ada vault for Tri-Chat CLI only."
echo "Run: ./scripts/adacode.sh"
