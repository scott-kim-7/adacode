from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from ada.agent.config import AgentConfig, load_agent_config
from ada.agent.tool_nodes import (
	make_execute_tool_node,
	make_finalize_node,
	make_prepare_node,
	make_tool_loop_node,
	tool_loop_decision,
)
from ada.agent.tool_state import ToolAgentState
from ada.llm import ChatCompletionResult, ChatMessage


def build_tool_agent_graph(
	tool_llm_callable: Callable[[list[ChatMessage], list[dict[str, Any]] | None], ChatCompletionResult],
	config: AgentConfig | None = None,
) -> Any:
	"""Compile ToolAgentGraph: prepare → tool_loop → [execute] → finalize."""
	cfg = config or load_agent_config()

	graph = StateGraph(ToolAgentState)
	graph.add_node("prepare", make_prepare_node(cfg))
	graph.add_node("tool_loop", make_tool_loop_node(cfg, tool_llm_callable))
	graph.add_node("execute_tool", make_execute_tool_node(cfg))
	graph.add_node("finalize", make_finalize_node(cfg))

	graph.add_edge(START, "prepare")
	graph.add_edge("prepare", "tool_loop")
	graph.add_conditional_edges(
		"tool_loop",
		tool_loop_decision,
		{"execute": "execute_tool", "finalize": "finalize"},
	)
	graph.add_edge("execute_tool", "tool_loop")
	graph.add_edge("finalize", END)

	return graph.compile()


def run_tool_agent_turn(
	messages: list[dict[str, Any]],
	tools: list[dict[str, Any]],
	tool_llm_callable: Callable[[list[ChatMessage], list[dict[str, Any]] | None], ChatCompletionResult],
	config: AgentConfig | None = None,
	*,
	auto_execute: bool = False,
) -> tuple[dict[str, Any], str]:
	"""Run tool agent. Default single-shot (benchmark harness handles tool loop)."""
	cfg = config or load_agent_config()
	if not auto_execute:
		result = tool_llm_callable(
			_openai_dicts_to_chat(_inject_system(messages, cfg)),
			tools or None,
		)
		assistant = _assistant_payload(result)
		return assistant, result.finish_reason

	compiled = build_tool_agent_graph(tool_llm_callable, config=cfg)
	state = compiled.invoke(
		{
			"openai_messages": list(messages),
			"tools": list(tools),
			"tool_rounds": 0,
			"done": False,
		}
	)
	assistant = state.get("assistant_message") or {"role": "assistant", "content": ""}
	finish = str(state.get("finish_reason") or "stop")
	return assistant, finish


def _inject_system(messages: list[dict[str, Any]], cfg: AgentConfig) -> list[dict[str, Any]]:
	if not messages:
		return messages
	if messages[0].get("role") == "system" or not cfg.system_prompt.strip():
		return messages
	return [{"role": "system", "content": cfg.system_prompt.strip()}, *messages]


def _openai_dicts_to_chat(messages: list[dict[str, Any]]) -> list[ChatMessage]:
	out: list[ChatMessage] = []
	for message in messages:
		if not isinstance(message, dict):
			continue
		role = str(message.get("role") or "user")
		content = message.get("content")
		tool_calls = message.get("tool_calls")
		parsed_calls = tuple(tool_calls) if isinstance(tool_calls, list) else None
		out.append(
			ChatMessage(
				role=role,
				content=content if content is not None else None,
				tool_calls=parsed_calls,
				tool_call_id=str(message["tool_call_id"]) if message.get("tool_call_id") else None,
				name=str(message["name"]) if message.get("name") else None,
			)
		)
	return out


def _assistant_payload(result: ChatCompletionResult) -> dict[str, Any]:
	payload: dict[str, Any] = {"role": "assistant"}
	if result.content is not None:
		payload["content"] = result.content
	if result.tool_calls:
		payload["tool_calls"] = result.tool_calls
	return payload
