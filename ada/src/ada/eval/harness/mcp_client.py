from __future__ import annotations

from typing import Any


def mcp_tool_to_openai(tool: dict[str, Any]) -> dict[str, Any]:
	"""Convert MCP tool definition to OpenAI function tool schema."""
	name = str(tool.get("name") or "")
	description = str(tool.get("description") or "")
	input_schema = tool.get("inputSchema") or tool.get("parameters") or {"type": "object", "properties": {}}
	return {
		"type": "function",
		"function": {
			"name": name,
			"description": description,
			"parameters": input_schema,
		},
	}


def openai_tools_from_mcp(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [mcp_tool_to_openai(tool) for tool in tools if isinstance(tool, dict)]
