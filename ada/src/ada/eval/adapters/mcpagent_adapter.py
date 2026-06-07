from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.mcp_client import openai_tools_from_mcp
from ada.eval.harness.results import make_result, write_result
from ada.registry import get_profile, load_registry


def _model_name() -> str:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	return get_profile(load_registry(), profile_name).model


def _sample_mcp_tools() -> list[dict[str, Any]]:
	return openai_tools_from_mcp(
		[
			{
				"name": "search_docs",
				"description": "Search documentation",
				"inputSchema": {
					"type": "object",
					"properties": {"query": {"type": "string"}},
					"required": ["query"],
				},
			},
			{
				"name": "distractor_calc",
				"description": "Calculator distractor tool",
				"inputSchema": {
					"type": "object",
					"properties": {"expr": {"type": "string"}},
				},
			},
		]
	)


def _fallback_smoke(num_tasks: int) -> dict[str, Any]:
	client = AgentEvalClient()
	passed = 0
	task_ids: list[str] = []
	tools = _sample_mcp_tools()
	start = time.monotonic()
	try:
		for idx in range(num_tasks):
			task_id = f"mcp-{idx + 1:03d}"
			task_ids.append(task_id)
			resp = client.chat(
				[
					{
						"role": "user",
						"content": "Find docs about authentication. Use search_docs, not calculator.",
					}
				],
				tools=tools,
			)
			message = resp.get("choices", [{}])[0].get("message", {})
			tool_calls = message.get("tool_calls") or []
			names = [
				str((call.get("function") or {}).get("name") or "")
				for call in tool_calls
				if isinstance(call, dict)
			]
			if "search_docs" in names or (message.get("content") or "").strip():
				passed += 1
	finally:
		client.close()
	duration = time.monotonic() - start
	return make_result(
		"mcpagent",
		"smoke",
		endpoint=eval_base_url(),
		model=_model_name(),
		tasks_total=num_tasks,
		tasks_passed=passed,
		duration_sec=duration,
		task_ids=task_ids,
		extra={"source": "harness-fallback"},
	)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("mcpagent") or {}
	smoke = bench.get("smoke") or {}
	num_tasks = int(smoke.get("num_tasks") or 5)
	out = output or results_dir() / "mcpagent-smoke.json"

	vendor = vendor_root() / "MCPAgentBench"
	if vendor.is_dir():
		# Wire vendor runner when official repo is pinned in install-vendors.sh
		pass

	payload = _fallback_smoke(num_tasks)
	write_result(out, payload)
	return payload


def run_full(output: Path | None = None) -> dict[str, Any]:
	return run_smoke(output=output or results_dir() / "mcpagent-full.json")
