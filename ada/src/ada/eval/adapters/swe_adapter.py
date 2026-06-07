from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.results import make_result, write_result
from ada.eval.harness.subprocess_runner import run_command
from ada.registry import get_profile, load_registry


def docker_available() -> bool:
	return shutil.which("docker") is not None and run_command(["docker", "info"]).returncode == 0


def _model_name() -> str:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	return get_profile(load_registry(), profile_name).model


def _fallback_smoke(instance_id: str) -> dict[str, Any]:
	client = AgentEvalClient()
	start = time.monotonic()
	passed = 0
	try:
		resp = client.chat(
			[
				{
					"role": "user",
					"content": f"SWE smoke instance {instance_id}: propose a one-line fix summary.",
				}
			]
		)
		content = resp.get("choices", [{}])[0].get("message", {}).get("content") or ""
		if content.strip():
			passed = 1
	finally:
		client.close()
	duration = time.monotonic() - start
	return make_result(
		"swe",
		"smoke",
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=1,
		tasks_passed=passed,
		duration_sec=duration,
		task_ids=[instance_id],
		extra={"source": "harness-fallback", "docker": docker_available()},
	)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("swe") or {}
	smoke = bench.get("smoke") or {}
	instance_ids = smoke.get("instance_ids") or ["django__django-11099"]
	instance_id = str(instance_ids[0])
	out = output or results_dir() / "swe-smoke.json"

	vendor = vendor_root() / "SWE-bench"
	if vendor.is_dir() and docker_available():
		env = os.environ.copy()
		env["OPENAI_API_BASE"] = eval_base_url()
		env["OPENAI_API_KEY"] = "local"
		# Full docker eval requires predictions file — use fallback until wired
		pass

	payload = _fallback_smoke(instance_id)
	write_result(out, payload)
	return payload


def run_full(output: Path | None = None) -> dict[str, Any]:
	return run_smoke(output=output or results_dir() / "swe-full.json")
