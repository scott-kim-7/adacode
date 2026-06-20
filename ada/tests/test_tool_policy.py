from __future__ import annotations

from ada.agent.tool_policy import (
	is_agent_tool_request,
	is_mcp_tool_request,
	is_native_tool_request,
)


def test_is_mcp_tool_request():
	meta = {"tool_ids": ["server:mcp:abc"]}
	tools = [{"type": "function", "function": {"name": "fn"}}]
	assert is_mcp_tool_request(meta, tools) is True
	assert is_native_tool_request(meta, tools) is False
	assert is_agent_tool_request(meta, tools) is True


def test_is_agent_tool_request_native():
	meta = {"tool_ids": ["tool-1"]}
	tools = [{"type": "function", "function": {"name": "fn"}}]
	assert is_agent_tool_request(meta, tools) is True


def test_tool_servers_not_agent_executed():
	meta = {"tool_servers": [{}]}
	tools = [{"type": "function", "function": {"name": "fn"}}]
	assert is_agent_tool_request(meta, tools) is False
