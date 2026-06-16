from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from ada.agent.config import AgentConfig, load_agent_config
from ada.agent.nodes import (
	bump_retry_node,
	finalize_node,
	plan_node,
	prepare_node,
	respond_decision,
	respond_node,
	route_decision,
	route_node,
)
from ada.agent.content import UserContent, content_is_empty, ensure_user_prompt
from ada.agent.state import AgentState
from ada.agent.stream_sink import StreamContext


def build_main_agent_graph(
	llm_callable: Callable[[list[BaseMessage]], str],
	config: AgentConfig | None = None,
	stream_context: StreamContext | None = None,
) -> Any:
	"""Compile MainGraph: prepare → route → [plan] → respond → verify → END."""
	cfg = config or load_agent_config()

	graph = StateGraph(AgentState)
	graph.add_node("prepare", prepare_node(cfg))
	graph.add_node("route", route_node(cfg))
	graph.add_node("plan", plan_node(cfg, llm_callable, stream_context))
	graph.add_node("respond", respond_node(cfg, llm_callable, stream_context))
	graph.add_node("bump_retry", bump_retry_node())
	graph.add_node("finalize", finalize_node(cfg))

	graph.add_edge(START, "prepare")
	graph.add_edge("prepare", "route")
	graph.add_conditional_edges(
		"route",
		route_decision,
		{"direct": "respond", "plan": "plan"},
	)
	graph.add_edge("plan", "respond")
	graph.add_conditional_edges(
		"respond",
		respond_decision(cfg),
		{"finalize": "finalize", "retry": "bump_retry"},
	)
	graph.add_edge("bump_retry", "respond")
	graph.add_edge("finalize", END)

	return graph.compile()


def build_simple_agent_graph(
	llm_callable: Callable[[list[BaseMessage]], str],
	config: AgentConfig | None = None,
	stream_context: StreamContext | None = None,
) -> Callable[[list[BaseMessage]], str]:
	"""Backward-compatible helper: run MainGraph on a message list."""
	compiled = build_main_agent_graph(
		llm_callable,
		config=config,
		stream_context=stream_context,
	)

	def run_turn(messages: list[BaseMessage]) -> str:
		result = compiled.invoke(
			{
				"messages": messages,
				"empty_retries": 0,
			}
		)
		final_messages = result.get("messages") or []
		for message in reversed(final_messages):
			if isinstance(message, AIMessage):
				content = message.content
				return content if isinstance(content, str) else str(content)
		return ""

	return run_turn


def run_user_turn(
	user_content: UserContent,
	history: list[BaseMessage],
	llm_callable: Callable[[list[BaseMessage]], str],
	config: AgentConfig | None = None,
	stream_context: StreamContext | None = None,
) -> tuple[str, list[BaseMessage]]:
	"""Append user message, run MainGraph, return assistant text and updated history."""
	if content_is_empty(user_content):
		return "", history

	cfg = config or load_agent_config()
	user_content = ensure_user_prompt(user_content, prompt=cfg.vision.image_only_prompt)

	compiled = build_main_agent_graph(
		llm_callable,
		config=cfg,
		stream_context=stream_context,
	)
	result = compiled.invoke(
		{
			"messages": [*history, HumanMessage(content=user_content)],
			"empty_retries": 0,
		}
	)
	updated = list(result.get("messages") or [])
	assistant_text = ""
	for message in reversed(updated):
		if isinstance(message, AIMessage):
			content = message.content
			assistant_text = content if isinstance(content, str) else str(content)
			break
	return assistant_text, updated
