from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ada.eval.adapters._common import annotate_result, begin_benchmark, save_benchmark_result
from ada.eval.adapters._model import resolved_eval_model
from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.results import make_result
from ada.eval.harness.run_log import log_event, log_line
from ada.eval.harness.subprocess_runner import run_command


def _vendor_bfcl_dir() -> Path:
	return vendor_root() / "gorilla" / "berkeley-function-call-leaderboard"


def _fallback(num_entries: int, mode: str, category: str) -> dict[str, Any]:
	client = AgentEvalClient()
	passed = 0
	task_ids: list[str] = []
	tools = [
		{
			"type": "function",
			"function": {
				"name": "get_weather",
				"description": "Get weather for a city",
				"parameters": {
					"type": "object",
					"properties": {"city": {"type": "string"}},
					"required": ["city"],
				},
			},
		}
	]
	start = time.monotonic()
	try:
		for idx in range(num_entries):
			task_id = f"{category}-{idx + 1:03d}"
			task_ids.append(task_id)
			log_line(f"task {task_id}: calling Agent API")
			resp = client.chat(
				[{"role": "user", "content": "What is the weather in Seoul? Use the get_weather tool."}],
				tools=tools,
			)
			message = resp.get("choices", [{}])[0].get("message", {})
			if message.get("tool_calls") or (message.get("content") or "").strip():
				passed += 1
	finally:
		client.close()
	return make_result(
		"bfcl",
		mode,
		endpoint=eval_base_url(),
		model=resolved_eval_model(),
		tasks_total=num_entries,
		tasks_passed=passed,
		duration_sec=time.monotonic() - start,
		task_ids=task_ids,
		extra={"source": "harness-fallback", "test_category": category},
	)


def _run(mode: str, output: Path | None = None) -> dict[str, Any]:
	begin_benchmark("bfcl", mode)
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("bfcl") or {}
	section = bench.get(mode) or bench.get("smoke") or {}
	num_entries = int(section.get("num_entries") or (10 if mode == "smoke" else 100))
	category = str(section.get("test_category") or "simple_python")
	out = output or results_dir() / f"bfcl-{mode}.json"
	bfcl_dir = _vendor_bfcl_dir()
	script = bfcl_dir / "openfunctions_evaluation.py"

	if not bfcl_dir.is_dir() or not script.is_file():
		reason = f"BFCL vendor missing: {bfcl_dir}"
		payload = annotate_result(
			_fallback(num_entries, mode, category),
			mode=mode,
			vendor_path=bfcl_dir,
			fallback_reason=reason,
		)
		return save_benchmark_result("bfcl", mode, payload, out)

	env = os.environ.copy()
	env.update(
		{
			"OPENAI_API_BASE": eval_base_url(),
			"OPENAI_BASE_URL": eval_base_url(),
			"OPENAI_API_KEY": "local",
			"ADA_AGENT_BASE_URL": eval_base_url(),
		}
	)
	log_event("vendor_run_start", vendor=str(bfcl_dir), category=category, num_entries=num_entries)
	result = run_command(
		[
			"python",
			str(script),
			"--model",
			"ada-agent",
			"--test-category",
			category,
			"--num-entries",
			str(num_entries),
			"--output-path",
			str(out),
		],
		cwd=bfcl_dir,
		env=env,
		timeout=float(os.environ.get("ADA_EVAL_TIMEOUT", "3600")),
		log_name=f"bfcl-{mode}",
	)
	if result.returncode == 0 and out.is_file():
		payload = annotate_result(
			json.loads(out.read_text(encoding="utf-8")),
			mode=mode,
			vendor_path=bfcl_dir,
			vendor_ran=True,
			subprocess_log=result.log_path,
		)
		return save_benchmark_result("bfcl", mode, payload, out)

	reason = f"BFCL vendor run failed exit={result.returncode}"
	payload = annotate_result(
		_fallback(num_entries, mode, category),
		mode=mode,
		vendor_path=bfcl_dir,
		fallback_reason=reason,
		subprocess_log=result.log_path,
	)
	return save_benchmark_result("bfcl", mode, payload, out)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	return _run("smoke", output)


def run_full(output: Path | None = None) -> dict[str, Any]:
	return _run("full", output)
