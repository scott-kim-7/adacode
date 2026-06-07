from __future__ import annotations

from typing import Any, TypedDict


class ToolAgentState(TypedDict, total=False):
	"""ToolAgentGraph state for tool-use completions."""

	openai_messages: list[dict[str, Any]]
	tools: list[dict[str, Any]]
	tool_rounds: int
	assistant_message: dict[str, Any]
	finish_reason: str
	done: bool
