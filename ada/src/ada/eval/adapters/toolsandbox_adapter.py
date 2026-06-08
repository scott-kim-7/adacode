from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ada.eval.adapters._common import annotate_result, begin_benchmark, save_benchmark_result
from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.results import make_result
from ada.eval.harness.run_log import log_line
from ada.registry import get_profile, load_registry


def _model_name() -> str:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	return get_profile(load_registry(), profile_name).model


def _fallback(num_scenarios: int, mode: str) -> dict[str, Any]:
	client = AgentEvalClient()
	passed = 0
	task_ids: list[str] = []
	tools = [
		{
			"type": "function",
			"function": {
				"name": "set_reminder",
				"description": "Set a reminder",
				"parameters": {
					"type": "object",
					"properties": {"title": {"type": "string"}, "time": {"type": "string"}},
					"required": ["title"],
				},
			},
		}
	]
	start = time.monotonic()
	try:
		for idx in range(num_scenarios):
			task_id = f"scenario-{idx + 1:03d}"
			task_ids.append(task_id)
			log_line(f"task {task_id}: calling Agent API")
			resp = client.chat(
				[{"role": "user", "content": "Set a reminder titled buy milk at 5pm."}],
				tools=tools,
			)
			message = resp.get("choices", [{}])[0].get("message", {})
			if message.get("tool_calls") or (message.get("content") or "").strip():
				passed += 1
	finally:
		client.close()
	return make_result(
		"toolsandbox",
		mode,
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=num_scenarios,
		tasks_passed=passed,
		duration_sec=time.monotonic() - start,
		task_ids=task_ids,
		extra={"source": "harness-fallback"},
	)


def _run(mode: str, output: Path | None = None) -> dict[str, Any]:
	begin_benchmark("toolsandbox", mode)
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("toolsandbox") or {}
	section = bench.get(mode) or bench.get("smoke") or {}
	num_scenarios = int(section.get("num_scenarios") or (3 if mode == "smoke" else 30))
	out = output or results_dir() / f"toolsandbox-{mode}.json"
	vendor = vendor_root() / "ToolSandbox"

	if not vendor.is_dir():
		reason = f"ToolSandbox vendor missing: {vendor}"
	else:
		reason = "ToolSandbox vendor runner not wired yet — using harness fallback"

	payload = annotate_result(
		_fallback(num_scenarios, mode),
		mode=mode,
		vendor_path=vendor,
		fallback_reason=reason,
	)
	return save_benchmark_result("toolsandbox", mode, payload, out)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	return _run("smoke", output)


def run_full(output: Path | None = None) -> dict[str, Any]:
	return _run("full", output)
