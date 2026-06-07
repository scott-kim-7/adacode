from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

Route = Literal["direct", "plan"]


class AgentState(TypedDict, total=False):
	"""MainGraph state — see docs/ada/agent/README.md."""

	messages: Annotated[list[BaseMessage], add_messages]
	route: Route
	plan: str
	draft: str
	empty_retries: int
