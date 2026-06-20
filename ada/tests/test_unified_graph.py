from __future__ import annotations

from unittest.mock import AsyncMock, patch

from ada.agent.config import load_agent_config
from ada.agent.openai_compat import run_unified_chat_completion
from ada.agent.tool_policy import is_native_tool_request
from ada.llm import ChatCompletionResult


def test_is_native_tool_request():
	meta = {}
	tools = [{"type": "function", "function": {"name": "fn"}}]
	assert is_native_tool_request(meta, tools) is True
	assert is_native_tool_request({"tool_servers": [{}]}, tools) is False


def test_unified_graph_chat_mock_llm():
	cfg = load_agent_config()
	metadata = {"features": {"memory": False, "web_search": False}}

	def chat_llm(messages):
		return "hello unified"

	def tool_llm(messages, tools=None):
		return ChatCompletionResult(content="x", finish_reason="stop")

	with patch("ada.agent.unified_nodes.asyncio.run", return_value=[]):
		result = run_unified_chat_completion(
			[{"role": "user", "content": "hi"}],
			metadata,
			chat_llm,
			tool_llm,
			cfg,
		)
	assert result == "hello unified"


def test_unified_tool_branch_returns_tool_calls():
	cfg = load_agent_config()
	metadata = {"tool_ids": ["tool-1"]}
	tools = [{"type": "function", "function": {"name": "noop", "parameters": {"type": "object", "properties": {}}}}]
	calls = {"n": 0}

	def chat_llm(messages):
		return "unused"

	def tool_llm(messages, tools=None):
		calls["n"] += 1
		if calls["n"] == 1:
			return ChatCompletionResult(
				content=None,
				finish_reason="tool_calls",
				tool_calls=(
					{
						"id": "call_1",
						"type": "function",
						"function": {"name": "noop", "arguments": "{}"},
					},
				),
			)
		return ChatCompletionResult(content="final", finish_reason="stop", tool_calls=None)

	with patch(
		"ada.agent.unified_nodes.asyncio.run",
		side_effect=lambda coro: (
			coro.close(),
			[{"role": "tool", "tool_call_id": "call_1", "name": "noop", "content": "{}"}],
		)[1],
	):
		with patch("ada.agent.unified_nodes.OwuiToolBackend") as backend_cls:
			backend_cls.return_value.execute = AsyncMock(return_value="{}")
			result = run_unified_chat_completion(
				[{"role": "user", "content": "run tool"}],
				metadata,
				chat_llm,
				tool_llm,
				cfg,
				openai_tools=tools,
			)
	assert result == "final"
