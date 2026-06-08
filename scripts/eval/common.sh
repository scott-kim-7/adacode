#!/usr/bin/env bash
# Shared env for Ada eval runners.
set -euo pipefail

EVAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$EVAL_DIR/../.." && pwd)"
ADA="$ROOT/ada"
VENV="$ADA/.venv"

export ROOT ADA VENV
export ADA_EVAL_BASE_URL="${ADA_EVAL_BASE_URL:-http://127.0.0.1:8082/v1}"
export ADA_EVAL_VENDOR_ROOT="${ADA_EVAL_VENDOR_ROOT:-$ROOT/.eval/vendor}"
export ADA_AGENT_PROFILE="${ADA_AGENT_PROFILE:-chat_profile}"

activate_venv() {
	if [[ ! -d "$VENV" ]]; then
		python3 -m venv "$VENV"
	fi
	# shellcheck disable=SC1091
	source "$VENV/bin/activate"
	pip install -q -e "$ADA[dev]"
}

resolve_model() {
	python - <<'PY'
from ada.registry import get_profile, load_registry
import os
profile_name = os.environ.get("ADA_AGENT_PROFILE", "chat_profile")
print(get_profile(load_registry(), profile_name).model)
PY
}

export ADA_EVAL_MODEL="${ADA_EVAL_MODEL:-$(resolve_model 2>/dev/null || echo ada-agent)}"

write_benchmark_report() {
	local benchmark="$1"
	local mode="$2"
	python - <<PY
from ada.eval.harness.report import write_benchmark_report
from ada.eval.harness.config import results_dir
import json
path = results_dir() / "${benchmark}-${mode}.json"
payload = json.loads(path.read_text(encoding="utf-8"))
report = write_benchmark_report(payload)
extra = payload.get("extra") or {}
if extra.get("fallback_reason"):
    print(f"WARN: fallback — {extra['fallback_reason']}", flush=True)
if extra.get("benchmark_log"):
    print(f"Log: {extra['benchmark_log']}", flush=True)
print(f"Report: {report}")
PY
}
