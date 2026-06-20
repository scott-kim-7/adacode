from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ada.agent.config import load_agent_config
from ada.agent.openai_compat import run_unified_chat_completion
from ada.agent.tool_policy import is_native_tool_request
from ada.llm import ChatCompletionResult
from ada.tools.owui_backend import OwuiToolBackend


def test_is_native_tool_request_rejects_mcp_tool_ids():
	tools = [{"type": "function", "function": {"name": "fn"}}]
	meta = {"tool_ids": ["server:mcp:abc"]}
	assert is_native_tool_request(meta, tools) is False


def test_owui_tool_backend_execute():
	backend = OwuiToolBackend(base_url="http://example.test")
	mock_response = type(
		"R",
		(),
		{
			"json": lambda self: {"content": "ok"},
			"raise_for_status": lambda self: None,
		},
	)()

	async def _run() -> None:
		with patch("httpx.AsyncClient") as client_cls:
			client = AsyncMock()
			client.__aenter__.return_value = client
			client.post.return_value = mock_response
			client_cls.return_value = client
			result = await backend.execute("noop", "{}", ["tool-1"], bytearray(b"Bearer x"))
		assert result == "ok"
		client.post.assert_awaited_once()

	asyncio.run(_run())


def _fake_asyncio_run_tool_messages(coro):
	coro.close()
	return [{"role": "tool", "tool_call_id": "call_1", "name": "noop", "content": "{}"}]


def test_unified_tool_execute_loop_returns_text():
	cfg = load_agent_config()
	metadata = {"tool_ids": ["tool-1"]}
	tools = [{"type": "function", "function": {"name": "noop", "parameters": {"type": "object", "properties": {}}}}]
	calls = {"n": 0}

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
		return ChatCompletionResult(content="done after tool", finish_reason="stop", tool_calls=None)

	with patch("ada.agent.unified_nodes.asyncio.run", side_effect=_fake_asyncio_run_tool_messages):
		with patch("ada.agent.unified_nodes.OwuiToolBackend") as backend_cls:
			backend_cls.return_value.execute = AsyncMock(return_value='{"ok": true}')
			result = run_unified_chat_completion(
				[{"role": "user", "content": "run"}],
				metadata,
				lambda m: "unused",
				tool_llm,
				cfg,
				openai_tools=tools,
			)
	assert result == "done after tool"
