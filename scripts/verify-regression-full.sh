#!/usr/bin/env bash
# Full Ada regression — contract + 5 benchmarks + eval pytest + consolidated report.
#
# Usage:
#   ./scripts/verify-regression-full.sh                    # smoke benchmarks (~10–30 min)
#   ./scripts/verify-regression-full.sh --start-stack      # start MLX/Agent if down
#   ./scripts/verify-regression-full.sh --update-baseline  # refresh baseline.json
#   ./scripts/verify-regression-full.sh --benchmark-mode full   # WARNING: days on local MLX
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADA="$ROOT/ada"
VENV="$ADA/.venv"
SCRIPTS="$ROOT/scripts"
REPORTS="$ADA/src/ada/eval/reports"
CONTRACT_JUNIT="$REPORTS/.tmp-contract-junit.xml"
EVAL_JUNIT="$REPORTS/.tmp-eval-smoke-junit.xml"
STEPS_JSON="$REPORTS/.tmp-full-regression-steps.json"

BENCHMARK_MODE="smoke"
START_STACK=0
UPDATE_BASELINE=0
SKIP_BENCHMARKS=0

usage() {
	cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --start-stack         Start MLX + Agent via ./scripts/ada.sh start if down
  --benchmark-mode MODE smoke (default) or full
  --update-baseline     Write benchmark results into baseline.json
  --skip-benchmarks     Skip live benchmark scripts (pytest + contract only)
  -h, --help            Show this help

Output:
  ada/src/ada/eval/reports/full-regression-latest.md
  ada/src/ada/eval/reports/summary-latest.md
  ada/src/ada/eval/logs/latest-full-regression-<mode>.log
  ada/src/ada/eval/logs/sessions/<timestamp>-full-regression-<mode>.log
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--start-stack) START_STACK=1 ;;
		--benchmark-mode)
			BENCHMARK_MODE="${2:?mode required}"
			shift
			;;
		--update-baseline) UPDATE_BASELINE=1 ;;
		--skip-benchmarks) SKIP_BENCHMARKS=1 ;;
		-h | --help)
			usage
			exit 0
			;;
		*)
			echo "Unknown option: $1" >&2
			usage
			exit 2
			;;
	esac
	shift
done

if [[ "$BENCHMARK_MODE" != "smoke" && "$BENCHMARK_MODE" != "full" ]]; then
	echo "Invalid --benchmark-mode: $BENCHMARK_MODE (use smoke or full)" >&2
	exit 2
fi

if [[ "$BENCHMARK_MODE" == "full" ]]; then
	echo "WARN: --benchmark-mode full may take days on local MLX."
fi

mkdir -p "$REPORTS"
echo "[]" >"$STEPS_JSON"

SESSION_LOG="$(python - <<PY
from ada.eval.harness.run_log import create_session_log
print(create_session_log("full-regression", "$BENCHMARK_MODE"))
PY
)"
export ADA_EVAL_SESSION_LOG="$SESSION_LOG"
exec > >(tee -a "$SESSION_LOG") 2>&1
echo "Session log: $SESSION_LOG"

if [[ ! -d "$VENV" ]]; then
	python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -e "$ADA[dev]"

export ADA_EVAL_BASE_URL="${ADA_EVAL_BASE_URL:-http://127.0.0.1:8082/v1}"
export ADA_AGENT_PROFILE="${ADA_AGENT_PROFILE:-chat_profile}"

STARTED_AT="$(python - <<'PY'
from datetime import UTC, datetime
print(datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
PY
)"
START_TS=$(date +%s)
FAILED=0

log_step() {
	local name="$1"
	local status="$2"
	local duration="$3"
	local error="${4:-}"
	python - <<PY
import json
from pathlib import Path
path = Path("$STEPS_JSON")
steps = json.loads(path.read_text(encoding="utf-8"))
steps.append({
    "name": """$name""",
    "status": "$status",
    "duration_sec": round(float("$duration"), 2),
    "error": """$error""",
})
path.write_text(json.dumps(steps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
}

run_step() {
	local name="$1"
	shift
	local t0 t1 rc duration
	echo ""
	echo "=== $name ==="
	t0=$(date +%s)
	set +e
	"$@"
	rc=$?
	set -e
	t1=$(date +%s)
	duration=$((t1 - t0))
	if [[ $rc -eq 0 ]]; then
		log_step "$name" "PASS" "$duration"
		echo "OK (${duration}s)"
	else
		FAILED=1
		log_step "$name" "FAIL" "$duration" "exit code $rc"
		echo "FAIL (${duration}s, exit $rc)" >&2
	fi
}

echo "=== Ada Full Regression ==="
echo "Mode: benchmark=$BENCHMARK_MODE"
echo "Started: $STARTED_AT"

# Stack check / optional start
STACK_JSON="$(python - <<'PY'
from ada.eval.harness.stack_check import stack_status
import json
print(json.dumps(stack_status()))
PY
)"
echo "Stack: $STACK_JSON"

AGENT_UP="$(python -c "import json; print(json.loads('''$STACK_JSON''')['agent_reachable'])")"
MLX_UP="$(python -c "import json; print(json.loads('''$STACK_JSON''')['mlx_reachable'])")"

if [[ "$AGENT_UP" != "True" || "$MLX_UP" != "True" ]]; then
	if [[ "$START_STACK" -eq 1 ]]; then
		run_step "Start stack (ada.sh start)" "$SCRIPTS/ada.sh" start
		sleep 5
	else
		echo ""
		echo "ERROR: Agent :8082 and MLX :8080 must be running for full regression." >&2
		echo "  ./scripts/ada.sh start" >&2
		echo "  or re-run with --start-stack" >&2
		exit 1
	fi
fi

export ADA_EVAL_RUN_LIVE=1

# Tier 1 — contract
run_step "Contract regression" \
	pytest "$ADA/tests/regression/" -m regression -q \
	--ignore="$ADA/tests/regression/eval" \
	--junitxml="$CONTRACT_JUNIT"

python -m ada.eval.harness.report contract --junit "$CONTRACT_JUNIT" >/dev/null

# Tier 2 — benchmarks ×5
if [[ "$SKIP_BENCHMARKS" -eq 0 ]]; then
	BENCH_SCRIPTS=(
		"τ²-bench:$SCRIPTS/eval/run-tau2-${BENCHMARK_MODE}.sh"
		"BFCL v4:$SCRIPTS/eval/run-bfcl-${BENCHMARK_MODE}.sh"
		"SWE-bench:$SCRIPTS/eval/run-swe-${BENCHMARK_MODE}.sh"
		"ToolSandbox:$SCRIPTS/eval/run-toolsandbox-${BENCHMARK_MODE}.sh"
		"MCPAgentBench:$SCRIPTS/eval/run-mcpagent-${BENCHMARK_MODE}.sh"
	)
	for entry in "${BENCH_SCRIPTS[@]}"; do
		label="${entry%%:*}"
		script="${entry#*:}"
		run_step "Benchmark: $label ($BENCHMARK_MODE)" "$script"
	done
fi

# Tier 2 — eval pytest
run_step "Eval pytest (live)" \
	pytest "$ADA/tests/regression/eval/" -m eval_smoke -q \
	--junitxml="$EVAL_JUNIT"

TOTAL_DURATION=$(($(date +%s) - START_TS))

UPDATE_FLAG=""
if [[ "$UPDATE_BASELINE" -eq 1 ]]; then
	UPDATE_FLAG="--update-baseline"
fi

REPORT="$(python -m ada.eval.harness.report full-regression \
	--junit "$CONTRACT_JUNIT" \
	--eval-junit "$EVAL_JUNIT" \
	--benchmark-mode "$BENCHMARK_MODE" \
	--started-at "$STARTED_AT" \
	--total-duration "$TOTAL_DURATION" \
	--steps-json "$STEPS_JSON" \
	$UPDATE_FLAG)"

echo ""
echo "=== Full Regression Complete ==="
echo "Report:  $REPORT"
echo "Summary: $REPORTS/summary-latest.md"
echo "Log:     $SESSION_LOG"
echo "Duration: ${TOTAL_DURATION}s"

if [[ $FAILED -ne 0 ]]; then
	echo ""
	echo "Some steps FAILED — see report for details." >&2
	exit 1
fi

echo ""
echo "All steps passed."
