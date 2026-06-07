from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from ada.agent.state import AgentState


def build_simple_agent_graph(
	llm_callable: Callable[[list[BaseMessage]], str],
) -> Callable[[list[BaseMessage]], str]:
	"""Compile START → llm → END (minimal LangGraph pass-through)."""

	def llm_node(state: AgentState) -> dict[str, list[BaseMessage]]:
		text = llm_callable(state["messages"])
		return {"messages": [AIMessage(content=text)]}

	graph = StateGraph(AgentState)
	graph.add_node("llm", llm_node)
	graph.add_edge(START, "llm")
	graph.add_edge("llm", END)
	compiled = graph.compile()

	def run_turn(messages: list[BaseMessage]) -> str:
		result = compiled.invoke({"messages": messages})
		final = result["messages"][-1]
		if isinstance(final, AIMessage):
			content = final.content
			return content if isinstance(content, str) else str(content)
		return str(final.content)

	return run_turn


def run_user_turn(
	user_text: str,
	history: list[BaseMessage],
	llm_callable: Callable[[list[BaseMessage]], str],
) -> tuple[str, list[BaseMessage]]:
	"""Append user message, run graph, return assistant text and updated history."""
	run_turn = build_simple_agent_graph(llm_callable)
	messages = [*history, HumanMessage(content=user_text)]
	assistant_text = run_turn(messages)
	updated = [*messages, AIMessage(content=assistant_text)]
	return assistant_text, updated
