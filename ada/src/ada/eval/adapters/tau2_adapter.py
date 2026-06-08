from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ada.eval.adapters._common import annotate_result, begin_benchmark, save_benchmark_result
from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.results import make_result
from ada.eval.harness.run_log import log_event, log_line
from ada.eval.harness.subprocess_runner import run_command
from ada.registry import get_profile, load_registry


def _model_name() -> str:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	return get_profile(load_registry(), profile_name).model


def _vendor_path() -> Path:
	return vendor_root() / "tau2-bench-verified"


def _fallback(num_tasks: int, mode: str, domain: str = "mock") -> dict[str, Any]:
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
			log_line(f"task {task_id}: calling Agent API")
			resp = client.chat(
				[{"role": "user", "content": f"{mode} task {task_id}: reply with ok."}],
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
		mode,
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=num_tasks,
		tasks_passed=passed,
		duration_sec=duration,
		task_ids=task_ids,
		extra={"source": "harness-fallback", "domain": domain},
	)


def _run(mode: str, output: Path | None = None) -> dict[str, Any]:
	begin_benchmark("tau2", mode)
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("tau2") or {}
	section = bench.get(mode) or bench.get("smoke") or {}
	num_tasks = int(section.get("num_tasks") or (5 if mode == "smoke" else 50))
	domain = str(section.get("domain") or section.get("domains") or "mock")
	if isinstance(domain, list):
		domain = ",".join(str(d) for d in domain)
	out = output or results_dir() / f"tau2-{mode}.json"
	vendor = _vendor_path()

	if not vendor.is_dir():
		reason = f"vendor missing: {vendor} (run ./scripts/eval/install-vendors.sh)"
		log_line(reason, level="WARN")
		payload = annotate_result(
			_fallback(num_tasks, mode, domain=str(domain)),
			mode=mode,
			vendor_path=vendor,
			fallback_reason=reason,
		)
		return save_benchmark_result("tau2", mode, payload, out)

	if not (vendor / "pyproject.toml").is_file():
		reason = f"vendor incomplete: {vendor} (no pyproject.toml)"
		payload = annotate_result(
			_fallback(num_tasks, mode, domain=str(domain)),
			mode=mode,
			vendor_path=vendor,
			fallback_reason=reason,
		)
		return save_benchmark_result("tau2", mode, payload, out)

	env = os.environ.copy()
	env["OPENAI_API_BASE"] = eval_base_url()
	env["OPENAI_BASE_URL"] = eval_base_url()
	env["OPENAI_API_KEY"] = "local"
	log_event("vendor_run_start", vendor=str(vendor), domain=domain, num_tasks=num_tasks)
	result = run_command(
		["uv", "run", "python", "-m", "tau2.run", "--domain", domain, "--num-tasks", str(num_tasks)],
		cwd=vendor,
		env=env,
		timeout=float(os.environ.get("ADA_EVAL_TIMEOUT", "7200")),
		log_name=f"tau2-{mode}",
	)
	if result.returncode == 0 and out.is_file():
		payload = json.loads(out.read_text(encoding="utf-8"))
		payload = annotate_result(
			payload,
			mode=mode,
			vendor_path=vendor,
			vendor_ran=True,
			subprocess_log=result.log_path,
		)
		return save_benchmark_result("tau2", mode, payload, out)

	reason = f"vendor run failed exit={result.returncode}"
	payload = annotate_result(
		_fallback(num_tasks, mode, domain=str(domain)),
		mode=mode,
		vendor_path=vendor,
		fallback_reason=reason,
		subprocess_log=result.log_path,
	)
	extra = dict(payload.get("extra") or {})
	extra["vendor_stderr_tail"] = (result.stderr or "")[-2000:]
	payload["extra"] = extra
	return save_benchmark_result("tau2", mode, payload, out)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	return _run("smoke", output)


def run_full(output: Path | None = None) -> dict[str, Any]:
	return _run("full", output)
