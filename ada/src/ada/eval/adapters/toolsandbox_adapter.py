from __future__ import annotations

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


def _fallback_smoke(num_scenarios: int) -> dict[str, Any]:
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
					"properties": {
						"title": {"type": "string"},
						"time": {"type": "string"},
					},
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
			resp = client.chat(
				[{"role": "user", "content": "Set a reminder titled buy milk at 5pm."}],
				tools=tools,
			)
			message = resp.get("choices", [{}])[0].get("message", {})
			if message.get("tool_calls") or (message.get("content") or "").strip():
				passed += 1
	finally:
		client.close()
	duration = time.monotonic() - start
	return make_result(
		"toolsandbox",
		"smoke",
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=num_scenarios,
		tasks_passed=passed,
		duration_sec=duration,
		task_ids=task_ids,
		extra={"source": "harness-fallback"},
	)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("toolsandbox") or {}
	smoke = bench.get("smoke") or {}
	num_scenarios = int(smoke.get("num_scenarios") or 3)
	out = output or results_dir() / "toolsandbox-smoke.json"

	vendor = vendor_root() / "ToolSandbox"
	if vendor.is_dir() and (vendor / "requirements.txt").is_file():
		env = os.environ.copy()
		env["OPENAI_API_BASE"] = eval_base_url()
		env["OPENAI_API_KEY"] = "local"
		# Vendor-specific entrypoint can be wired when repo layout confirmed
		_ = run_command(["python", "--version"], cwd=vendor, env=env)

	payload = _fallback_smoke(num_scenarios)
	write_result(out, payload)
	return payload


def run_full(output: Path | None = None) -> dict[str, Any]:
	return run_smoke(output=output or results_dir() / "toolsandbox-full.json")
