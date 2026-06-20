from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ada.agent.server import create_app
from ada.agent.tool_graph import run_tool_agent_turn
from ada.eval.harness.config import results_dir
from ada.eval.harness.results import compare_baseline, validate_result_schema
from ada.eval.harness.stack_check import is_agent_reachable, stack_status
from ada.llm import ChatCompletionResult, ChatMessage


pytestmark = pytest.mark.eval_smoke


def test_stack_reachable_or_skip():
	if not is_agent_reachable():
		pytest.skip("Agent API :9082 not reachable")
	status = stack_status()
	assert status["agent_reachable"] is True


def test_server_accepts_tools_field():
	app = create_app()

	def fake_unified(
		messages,
		metadata,
		chat_llm,
		tool_llm,
		config=None,
		stream_context=None,
		vault_session=None,
		openai_tools=None,
	):
		return "ok"

	with patch("ada.agent.server.run_unified_chat_completion", side_effect=fake_unified):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [{"role": "user", "content": "hi"}],
				"tools": [
					{
						"type": "function",
						"function": {
							"name": "noop",
							"parameters": {"type": "object", "properties": {}},
						},
					}
				],
			},
		)

	assert resp.status_code == 200
	body = resp.json()
	assert body["choices"][0]["message"]["role"] == "assistant"


def test_tool_loop_mock_roundtrip():
	calls = {"n": 0}

	def mock_tool_llm(messages: list[ChatMessage], tools):
		calls["n"] += 1
		if calls["n"] == 1:
			return ChatCompletionResult(
				content=None,
				tool_calls=[
					{
						"id": "call_1",
						"type": "function",
						"function": {"name": "noop", "arguments": "{}"},
					}
				],
				finish_reason="tool_calls",
			)
		return ChatCompletionResult(content="done", tool_calls=None, finish_reason="stop")

	assistant, finish = run_tool_agent_turn(
		[{"role": "user", "content": "run noop"}],
		[
			{
				"type": "function",
				"function": {
					"name": "noop",
					"parameters": {"type": "object", "properties": {}},
				},
			}
		],
		mock_tool_llm,
		auto_execute=True,
	)
	assert finish in {"stop", "tool_calls"}
	assert assistant.get("content") == "done" or assistant.get("tool_calls")


def test_eval_result_schema_and_baseline():
	sample = {
		"benchmark": "tau2",
		"mode": "smoke",
		"timestamp": "2026-06-06T00:00:00Z",
		"endpoint": "http://127.0.0.1:9082/v1",
		"model": "test-model",
		"tasks_total": 5,
		"tasks_passed": 5,
		"pass_rate": 1.0,
		"duration_sec": 1.0,
		"task_ids": ["mock-001"],
	}
	validate_result_schema(sample)
	ok, _ = compare_baseline("tau2", 1.0)
	assert ok is True
	path = results_dir() / "schema-test.json"
	path.write_text(json.dumps(sample), encoding="utf-8")
	assert path.is_file()


def test_report_contract_generation(tmp_path, monkeypatch):
	from ada.eval.harness import report as report_mod

	monkeypatch.setattr(report_mod, "reports_dir", lambda: tmp_path / "reports")
	junit = tmp_path / "junit.xml"
	junit.write_text(
		"""<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="2" failures="0" errors="0" skipped="0" time="0.5">
  <testcase classname="tests" name="test_ok" time="0.2"/>
  <testcase classname="tests" name="test_ok2" time="0.3"/>
</testsuite>""",
		encoding="utf-8",
	)
	path = report_mod.write_contract_report(junit_path=junit)
	assert path.is_file()
	text = path.read_text(encoding="utf-8")
	assert "Contract Regression" in text
	assert "**PASS**" in text
