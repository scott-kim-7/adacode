#!/usr/bin/env bash
# Ada regression suite — contracts that must not break between releases.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADA="$ROOT/ada"
VENV="$ADA/.venv"
JUNIT="$ADA/src/ada/eval/reports/.tmp-contract-junit.xml"

echo "=== Ada regression tests ==="

if [[ ! -d "$VENV" ]]; then
	python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -e "$ADA[dev]"

mkdir -p "$(dirname "$JUNIT")"

echo ""
pytest "$ADA/tests/regression/" -m regression -q --ignore="$ADA/tests/regression/eval" --junitxml="$JUNIT"

echo ""
REPORT="$(python -m ada.eval.harness.report contract --junit "$JUNIT")"
echo "Report: $REPORT"
echo ""
echo "Regression passed."
