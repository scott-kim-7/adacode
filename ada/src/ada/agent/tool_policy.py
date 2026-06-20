from __future__ import annotations

from typing import Any


def _tool_ids(metadata: dict[str, Any]) -> list[str]:
	raw = metadata.get("tool_ids")
	if not isinstance(raw, list):
		return []
	return [str(tool_id) for tool_id in raw]


def is_mcp_tool_request(metadata: dict[str, Any], tools: list[dict[str, Any]] | None) -> bool:
	if not tools:
		return False
	if metadata.get("tool_servers"):
		return False
	return any(tool_id.startswith("server:mcp:") for tool_id in _tool_ids(metadata))


def is_native_tool_request(metadata: dict[str, Any], tools: list[dict[str, Any]] | None) -> bool:
	if not tools:
		return False
	if metadata.get("tool_servers"):
		return False
	if is_mcp_tool_request(metadata, tools):
		return False
	return all(isinstance(tool, dict) and tool.get("type") == "function" for tool in tools)


def is_agent_tool_request(metadata: dict[str, Any], tools: list[dict[str, Any]] | None) -> bool:
	if not tools:
		return False
	if metadata.get("tool_servers"):
		return False
	return is_native_tool_request(metadata, tools) or is_mcp_tool_request(metadata, tools)
