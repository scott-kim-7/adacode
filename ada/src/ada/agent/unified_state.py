from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from ada.agent.state import Route


class UnifiedAgentState(TypedDict, total=False):
	messages: Annotated[list[BaseMessage], add_messages]
	metadata: dict[str, Any]
	memory_context: str
	search_items: list[dict[str, Any]]
	retrieve_sources: list[dict[str, Any]]
	openai_tools: list[dict[str, Any]]
	openai_messages: list[dict[str, Any]]
	tool_assistant: dict[str, Any]
	tool_finish_reason: str
	use_tool_branch: bool
	tool_rounds: int
	tool_done: bool
	assistant_message: dict[str, Any]
	route: Route
	plan: str
	draft: str
	empty_retries: int
