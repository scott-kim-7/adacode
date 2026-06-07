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


def _vendor_path() -> Path:
	return vendor_root() / "tau2-bench-verified"


def _fallback_smoke(num_tasks: int) -> dict[str, Any]:
	client = AgentEvalClient()
	passed = 0
	task_ids: list[str] = []
	tools = [
		{
			"type": "function",
			"function": {
				"name": "noop",
				"description": "No-op tool for smoke",
				"parameters": {"type": "object", "properties": {}},
			},
		}
	]
	start = time.monotonic()
	try:
		for idx in range(num_tasks):
			task_id = f"mock-{idx + 1:03d}"
			task_ids.append(task_id)
			resp = client.chat(
				[{"role": "user", "content": f"Smoke task {task_id}: reply with ok."}],
				tools=tools,
			)
			content = resp.get("choices", [{}])[0].get("message", {}).get("content") or ""
			if content.strip():
				passed += 1
	finally:
		client.close()
	duration = time.monotonic() - start
	return make_result(
		"tau2",
		"smoke",
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=num_tasks,
		tasks_passed=passed,
		duration_sec=duration,
		task_ids=task_ids,
		extra={"source": "harness-fallback", "domain": "mock"},
	)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("tau2") or {}
	smoke = bench.get("smoke") or {}
	num_tasks = int(smoke.get("num_tasks") or 5)
	domain = str(smoke.get("domain") or "mock")
	out = output or results_dir() / "tau2-smoke.json"

	vendor = _vendor_path()
	if vendor.is_dir() and (vendor / "pyproject.toml").is_file():
		env = os.environ.copy()
		env["OPENAI_API_BASE"] = eval_base_url()
		env["OPENAI_BASE_URL"] = eval_base_url()
		env["OPENAI_API_KEY"] = "local"
		start = time.monotonic()
		result = run_command(
			["uv", "run", "python", "-m", "tau2.run", "--domain", domain, "--num-tasks", str(num_tasks)],
			cwd=vendor,
			env=env,
			timeout=float(os.environ.get("ADA_EVAL_TIMEOUT", "7200")),
		)
		if result.returncode == 0 and out.is_file():
			import json

			payload = json.loads(out.read_text(encoding="utf-8"))
			return payload
		# vendor run failed — fall back
		payload = _fallback_smoke(num_tasks)
		payload["extra"] = {
			"source": "harness-fallback-after-vendor-failure",
			"vendor_stderr": result.stderr[-2000:],
		}
		write_result(out, payload)
		return payload

	payload = _fallback_smoke(num_tasks)
	write_result(out, payload)
	return payload


def run_full(output: Path | None = None) -> dict[str, Any]:
	return run_smoke(output=output or results_dir() / "tau2-full.json")
