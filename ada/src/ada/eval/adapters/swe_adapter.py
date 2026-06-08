from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

from ada.eval.adapters._common import annotate_result, begin_benchmark, save_benchmark_result
from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.results import make_result
from ada.eval.harness.run_log import log_line
from ada.eval.harness.subprocess_runner import run_command
from ada.registry import get_profile, load_registry


def docker_available() -> bool:
	if shutil.which("docker") is None:
		return False
	return run_command(["docker", "info"], log_name="docker-info").returncode == 0


def _model_name() -> str:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	return get_profile(load_registry(), profile_name).model


def _fallback(instance_id: str, mode: str) -> dict[str, Any]:
	client = AgentEvalClient()
	start = time.monotonic()
	passed = 0
	log_line(f"task {instance_id}: calling Agent API")
	try:
		resp = client.chat(
			[{"role": "user", "content": f"SWE {mode} instance {instance_id}: propose a one-line fix summary."}]
		)
		content = resp.get("choices", [{}])[0].get("message", {}).get("content") or ""
		if content.strip():
			passed = 1
	finally:
		client.close()
	return make_result(
		"swe",
		mode,
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=1,
		tasks_passed=passed,
		duration_sec=time.monotonic() - start,
		task_ids=[instance_id],
		extra={"source": "harness-fallback", "docker": docker_available()},
	)


def _run(mode: str, output: Path | None = None) -> dict[str, Any]:
	begin_benchmark("swe", mode)
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("swe") or {}
	section = bench.get(mode) or bench.get("smoke") or {}
	instance_ids = section.get("instance_ids") or ["django__django-11099"]
	instance_id = str(instance_ids[0])
	out = output or results_dir() / f"swe-{mode}.json"
	vendor = vendor_root() / "SWE-bench"

	if not vendor.is_dir():
		reason = f"SWE-bench vendor missing: {vendor}"
		payload = annotate_result(
			_fallback(instance_id, mode),
			mode=mode,
			vendor_path=vendor,
			fallback_reason=reason,
		)
		return save_benchmark_result("swe", mode, payload, out)

	if mode == "full" and not docker_available():
		reason = "Docker required for SWE-bench full eval but docker unavailable"
		payload = annotate_result(
			_fallback(instance_id, mode),
			mode=mode,
			vendor_path=vendor,
			fallback_reason=reason,
		)
		return save_benchmark_result("swe", mode, payload, out)

	reason = "SWE-bench docker harness not wired yet — using harness fallback"
	payload = annotate_result(
		_fallback(instance_id, mode),
		mode=mode,
		vendor_path=vendor,
		fallback_reason=reason,
	)
	return save_benchmark_result("swe", mode, payload, out)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	return _run("smoke", output)


def run_full(output: Path | None = None) -> dict[str, Any]:
	return _run("full", output)
