from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
from ada.agent.stream_sink import StreamContext
from ada.agent.unified_nodes import (
	make_inject_context_node,
	make_memory_gate_node,
	make_owui_execute_tool_node,
	make_retrieve_gate_node,
	make_retrieve_node,
	make_search_batch_node,
	make_search_gate_node,
	make_tool_finalize_node,
	make_tool_loop_node,
	retrieve_gate_decision,
	search_gate_decision,
	tool_gate_decision,
	unified_tool_loop_decision,
)
from ada.agent.unified_state import UnifiedAgentState
from ada.vault import VaultSession


def build_unified_chat_graph(
	chat_llm_callable: Callable[..., Any],
	tool_llm_callable: Callable[..., Any],
	config: AgentConfig | None = None,
	stream_context: StreamContext | None = None,
	vault_session: VaultSession | None = None,
) -> Any:
	cfg = config or load_agent_config()

	graph = StateGraph(UnifiedAgentState)
	graph.add_node("prepare", prepare_node(cfg))
	graph.add_node("memory_gate", make_memory_gate_node())
	graph.add_node("search_gate", make_search_gate_node())
	graph.add_node("search_batch", make_search_batch_node(vault_session))
	graph.add_node("retrieve_gate", make_retrieve_gate_node())
	graph.add_node("retrieve", make_retrieve_node())
	graph.add_node("inject_context", make_inject_context_node())
	graph.add_node("route", route_node(cfg, stream_context))
	graph.add_node("plan", plan_node(cfg, chat_llm_callable, stream_context))
	graph.add_node("tool_loop", make_tool_loop_node(tool_llm_callable))
	graph.add_node("execute_tool", make_owui_execute_tool_node())
	graph.add_node("tool_finalize", make_tool_finalize_node())
	graph.add_node("respond", respond_node(cfg, chat_llm_callable, stream_context))
	graph.add_node("bump_retry", bump_retry_node(stream_context))
	graph.add_node("finalize", finalize_node(cfg))

	graph.add_edge(START, "prepare")
	graph.add_edge("prepare", "memory_gate")
	graph.add_edge("memory_gate", "search_gate")
	graph.add_conditional_edges(
		"search_gate",
		search_gate_decision,
		{"search_batch": "search_batch", "retrieve_gate": "retrieve_gate"},
	)
	graph.add_edge("search_batch", "retrieve_gate")
	graph.add_conditional_edges(
		"retrieve_gate",
		retrieve_gate_decision,
		{"retrieve": "retrieve", "inject_context": "inject_context"},
	)
	graph.add_edge("retrieve", "inject_context")
	graph.add_conditional_edges(
		"inject_context",
		tool_gate_decision,
		{"tool_loop": "tool_loop", "route": "route"},
	)
	graph.add_conditional_edges(
		"tool_loop",
		unified_tool_loop_decision,
		{"execute_tool": "execute_tool", "tool_finalize": "tool_finalize"},
	)
	graph.add_edge("execute_tool", "tool_loop")
	graph.add_edge("tool_finalize", END)
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
