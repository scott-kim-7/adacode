from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ada.eval.harness.config import results_dir
from ada.eval.harness.results import compare_baseline, validate_result_schema
from ada.eval.harness.subprocess_runner import load_json_file

pytestmark = pytest.mark.eval_smoke


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[4]


@pytest.fixture
def require_stack(require_live_eval):
	del require_live_eval


def test_tau2_smoke_script(require_stack):
	script = _repo_root() / "scripts" / "eval" / "run-tau2-smoke.sh"
	result = subprocess.run([str(script)], capture_output=True, text=True, check=False)
	assert result.returncode == 0, result.stderr
	out = results_dir() / "tau2-smoke.json"
	assert out.is_file()
	payload = load_json_file(out)
	validate_result_schema(payload)
	ok, msg = compare_baseline("tau2", float(payload["pass_rate"]))
	assert ok, msg
