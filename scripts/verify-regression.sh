#!/usr/bin/env bash
# Ada regression suite — contracts that must not break between releases.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADA="$ROOT/ada"
VENV="$ADA/.venv"

echo "=== Ada regression tests ==="

if [[ ! -d "$VENV" ]]; then
	python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -e "$ADA[dev]"

echo ""
pytest "$ADA/tests/regression/" -m regression -q

echo ""
echo "Regression passed."
