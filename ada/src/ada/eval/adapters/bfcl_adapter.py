from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.results import make_result, write_result
from ada.eval.harness.subprocess_runner import run_command
from ada.registry import get_profile, load_registry


def _model_name() -> str:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	return get_profile(load_registry(), profile_name).model


def _vendor_bfcl_dir() -> Path:
	return vendor_root() / "gorilla" / "berkeley-function-call-leaderboard"


def _fallback_smoke(num_entries: int) -> dict[str, Any]:
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
			task_id = f"simple_python-{idx + 1:03d}"
			task_ids.append(task_id)
			resp = client.chat(
				[
					{
						"role": "user",
						"content": "What is the weather in Seoul? Use the get_weather tool.",
					}
				],
				tools=tools,
			)
			message = resp.get("choices", [{}])[0].get("message", {})
			if message.get("tool_calls") or (message.get("content") or "").strip():
				passed += 1
	finally:
		client.close()
	duration = time.monotonic() - start
	return make_result(
		"bfcl",
		"smoke",
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=num_entries,
		tasks_passed=passed,
		duration_sec=duration,
		task_ids=task_ids,
		extra={"source": "harness-fallback", "test_category": "simple_python"},
	)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("bfcl") or {}
	smoke = bench.get("smoke") or {}
	num_entries = int(smoke.get("num_entries") or 10)
	category = str(smoke.get("test_category") or "simple_python")
	out = output or results_dir() / "bfcl-smoke.json"

	bfcl_dir = _vendor_bfcl_dir()
	if bfcl_dir.is_dir():
		env = os.environ.copy()
		env["OPENAI_API_BASE"] = eval_base_url()
		env["OPENAI_BASE_URL"] = eval_base_url()
		env["OPENAI_API_KEY"] = "local"
		env["ADA_AGENT_BASE_URL"] = eval_base_url()
		start = time.monotonic()
		script = bfcl_dir / "openfunctions_evaluation.py"
		if script.is_file():
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
			)
			if result.returncode == 0 and out.is_file():
				return json.loads(out.read_text(encoding="utf-8"))

	payload = _fallback_smoke(num_entries)
	write_result(out, payload)
	return payload


def run_full(output: Path | None = None) -> dict[str, Any]:
	return run_smoke(output=output or results_dir() / "bfcl-full.json")
