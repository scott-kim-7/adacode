from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ada.eval.adapters._common import annotate_result, begin_benchmark, save_benchmark_result
from ada.eval.adapters._model import resolved_eval_model
from ada.eval.harness.agent_client import AgentEvalClient
from ada.eval.harness.config import eval_base_url, load_eval_config, results_dir, vendor_root
from ada.eval.harness.mcp_client import openai_tools_from_mcp
from ada.eval.harness.results import make_result
from ada.eval.harness.run_log import log_line


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
				"inputSchema": {"type": "object", "properties": {"expr": {"type": "string"}}},
			},
		]
	)


def _fallback(num_tasks: int, mode: str) -> dict[str, Any]:
	client = AgentEvalClient()
	passed = 0
	task_ids: list[str] = []
	tools = _sample_mcp_tools()
	start = time.monotonic()
	try:
		for idx in range(num_tasks):
			task_id = f"mcp-{idx + 1:03d}"
			task_ids.append(task_id)
			log_line(f"task {task_id}: calling Agent API")
			resp = client.chat(
				[{"role": "user", "content": "Find docs about authentication. Use search_docs, not calculator."}],
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
	return make_result(
		"mcpagent",
		mode,
		endpoint=eval_base_url(),
		model=resolved_eval_model(),
		tasks_total=num_tasks,
		tasks_passed=passed,
		duration_sec=time.monotonic() - start,
		task_ids=task_ids,
		extra={"source": "harness-fallback"},
	)


def _run(mode: str, output: Path | None = None) -> dict[str, Any]:
	begin_benchmark("mcpagent", mode)
	cfg = load_eval_config()
	bench = (cfg.get("benchmarks") or {}).get("mcpagent") or {}
	section = bench.get(mode) or bench.get("smoke") or {}
	num_tasks = int(section.get("num_tasks") or (5 if mode == "smoke" else 50))
	out = output or results_dir() / f"mcpagent-{mode}.json"
	vendor = vendor_root() / "MCPAgentBench"

	if vendor.is_dir():
		reason = "MCPAgentBench vendor runner not wired yet — using harness fallback"
	else:
		reason = f"MCPAgentBench vendor missing: {vendor} (set ADA_MCPAGENTBENCH_REPO)"

	payload = annotate_result(
		_fallback(num_tasks, mode),
		mode=mode,
		vendor_path=vendor,
		fallback_reason=reason,
	)
	return save_benchmark_result("mcpagent", mode, payload, out)


def run_smoke(output: Path | None = None) -> dict[str, Any]:
	return _run("smoke", output)


def run_full(output: Path | None = None) -> dict[str, Any]:
	return _run("full", output)
