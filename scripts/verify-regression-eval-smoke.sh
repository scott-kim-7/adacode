#!/usr/bin/env bash
# Ada eval smoke regression — requires Agent :9082 + MLX :8080 for live runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADA="$ROOT/ada"
VENV="$ADA/.venv"

echo "=== Ada eval smoke regression ==="

if [[ ! -d "$VENV" ]]; then
	python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -e "$ADA[dev]"

export ADA_EVAL_BASE_URL="${ADA_EVAL_BASE_URL:-http://127.0.0.1:9082/v1}"
export ADA_AGENT_PROFILE="${ADA_AGENT_PROFILE:-chat_profile}"

echo ""
echo "Stack check (MLX :8080, Agent :9082)..."
python - <<'PY'
from ada.eval.harness.stack_check import require_agent_stack
require_agent_stack()
print("Stack OK — enabling live eval smoke (ADA_EVAL_RUN_LIVE=1).")
open("/tmp/ada_eval_live", "w").write("1")
PY
if [[ -f /tmp/ada_eval_live ]]; then
	export ADA_EVAL_RUN_LIVE=1
	rm -f /tmp/ada_eval_live
fi

echo ""
JUNIT="$ADA/src/ada/eval/reports/.tmp-eval-smoke-junit.xml"
mkdir -p "$(dirname "$JUNIT")"
pytest "$ADA/tests/regression/eval/" -m eval_smoke -q --junitxml="$JUNIT"

echo ""
REPORT="$(python -m ada.eval.harness.report eval-smoke --junit "$JUNIT")"
echo "Report: $REPORT"
echo ""
echo "Eval smoke regression finished."
