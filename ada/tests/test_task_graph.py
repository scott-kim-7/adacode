from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from ada.agent.classify import classify_request, parse_request_metadata
from ada.agent.config import load_agent_config
from ada.agent.server import create_app
from ada.agent.task_graph import run_task_completion
from ada.owui_adapt.task_templates import (
	TASK_AUTOCOMPLETE_GENERATION,
	TASK_FOLLOW_UP_GENERATION,
	TASK_QUERY_GENERATION,
	TASK_TAGS_GENERATION,
	TASK_TITLE_GENERATION,
	heuristic_query_generation,
)


def test_classify_task_from_header():
	headers = {"X-Ada-Request-Kind": "task"}
	assert classify_request(headers, {"messages": [{"role": "user", "content": "hi"}]}) == "task"


def test_classify_task_from_metadata_header():
	import json

	meta = {"task": TASK_TITLE_GENERATION, "chat_id": "c1"}
	headers = {"X-OpenWebUI-Metadata": json.dumps(meta)}
	payload = {"messages": [{"role": "user", "content": "hi"}]}
	assert classify_request(headers, payload) == "task"


def test_classify_tool_from_payload():
	payload = {
		"messages": [{"role": "user", "content": "hi"}],
		"tools": [{"type": "function", "function": {"name": "fn"}}],
	}
	assert classify_request({}, payload) == "tool"


def test_parse_request_metadata_from_payload_fallback():
	payload = {
		"metadata": {"task": TASK_TITLE_GENERATION},
		"messages": [],
	}
	meta = parse_request_metadata({}, payload)
	assert meta["task"] == TASK_TITLE_GENERATION


def test_run_task_completion_title_one_llm_call():
	calls: list[list] = []

	def fake_llm(messages):
		calls.append(messages)
		return "My Chat Title"

	cfg = load_agent_config()
	payload = {
		"messages": [{"role": "user", "content": "ignored"}],
	}
	metadata = {
		"task": TASK_TITLE_GENERATION,
		"task_body": {
			"messages": [
				{"role": "user", "content": "How do I use Python?"},
				{"role": "assistant", "content": "Here is help."},
			],
		},
	}
	result = run_task_completion(payload, metadata, fake_llm, cfg)
	assert result == "My Chat Title"
	assert len(calls) == 1
	assert "Python" in str(calls[0][0].content)


def test_task_route_via_api_no_plan_trace():
	app = create_app()
	calls: list[list] = []

	def fake_llm(messages):
		calls.append(messages)
		return "Title Here"

	with patch.dict(
		app.state.llm_registry,
		{"task": fake_llm},
		clear=False,
	):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			headers={"X-Ada-Request-Kind": "task"},
			json={
				"model": "mlx-coder",
				"messages": [{"role": "user", "content": "x"}],
				"metadata": {
					"task": TASK_TITLE_GENERATION,
					"task_body": {"messages": [{"role": "user", "content": "hello"}]},
				},
			},
		)
	assert resp.status_code == 200
	body = resp.json()
	assert body["choices"][0]["message"]["content"] == "Title Here"
	assert len(calls) == 1


def test_ops_get_models():
	app = create_app()
	client = TestClient(app)
	resp = client.get("/ops/agent/models")
	assert resp.status_code == 200
	data = resp.json()
	assert data["chat"]["model_id"] == "mlx-coder"
	assert data["task"]["base_url"].endswith("/v1")


def test_run_task_completion_tags_one_llm_call():
	calls: list[list] = []

	def fake_llm(messages):
		calls.append(messages)
		return '{"tags": ["Science", "Python"]}'

	cfg = load_agent_config()
	payload = {"messages": []}
	metadata = {
		"task": TASK_TAGS_GENERATION,
		"task_body": {"messages": [{"role": "user", "content": "Explain Python"}]},
	}
	result = run_task_completion(payload, metadata, fake_llm, cfg)
	assert result == '{"tags": ["Science", "Python"]}'
	assert len(calls) == 1


def test_run_task_completion_follow_up_one_llm_call():
	calls: list[list] = []

	def fake_llm(messages):
		calls.append(messages)
		return '{"follow_ups": ["What is asyncio?"]}'

	cfg = load_agent_config()
	result = run_task_completion(
		{"messages": []},
		{
			"task": TASK_FOLLOW_UP_GENERATION,
			"task_body": {"messages": [{"role": "user", "content": "async in python"}]},
		},
		fake_llm,
		cfg,
	)
	assert "asyncio" in result
	assert len(calls) == 1


def test_run_task_completion_autocomplete_one_llm_call():
	calls: list[list] = []

	def fake_llm(messages):
		calls.append(messages)
		return '{"text": " world"}'

	cfg = load_agent_config()
	result = run_task_completion(
		{"messages": []},
		{
			"task": TASK_AUTOCOMPLETE_GENERATION,
			"task_body": {
				"messages": [{"role": "user", "content": "hello"}],
				"prompt": "hello",
				"type": "General",
			},
		},
		fake_llm,
		cfg,
	)
	assert result == '{"text": " world"}'
	assert len(calls) == 1
	assert "hello" in str(calls[0][0].content)


def test_query_generation_heuristic_no_llm():
	messages = [{"role": "user", "content": "search this topic"}]
	result = heuristic_query_generation(messages)
	assert '"queries"' in result
	assert "search this topic" in result

	cfg = load_agent_config()
	calls: list[list] = []

	def fake_llm(messages):
		calls.append(messages)
		return "should not run"

	result = run_task_completion(
		{"messages": messages},
		{"task": TASK_QUERY_GENERATION, "task_body": {"messages": messages}},
		fake_llm,
		cfg,
	)
	assert result == heuristic_query_generation(messages)
	assert len(calls) == 0


def test_title_json_normalized_to_plain_text():
	def fake_llm(messages):
		return '{"title": "📉 Markets"}'

	cfg = load_agent_config()
	result = run_task_completion(
		{"messages": []},
		{
			"task": TASK_TITLE_GENERATION,
			"task_body": {"messages": [{"role": "user", "content": "stocks"}]},
		},
		fake_llm,
		cfg,
	)
	assert result == "📉 Markets"
