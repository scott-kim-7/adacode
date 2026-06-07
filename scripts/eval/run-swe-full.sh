#!/usr/bin/env bash
set -euo pipefail
EVAL_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$EVAL_DIR/common.sh"
activate_venv
python - <<'PY'
from ada.eval.adapters.swe_adapter import run_full
payload = run_full()
print(f"swe full: {payload['tasks_passed']}/{payload['tasks_total']} pass_rate={payload['pass_rate']:.3f}")
PY
write_benchmark_report swe full