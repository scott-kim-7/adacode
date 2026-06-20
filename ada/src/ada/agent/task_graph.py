from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from ada.agent.config import AgentConfig
from ada.owui_adapt.task_templates import (
	SUPPORTED_TASK_KINDS,
	TASK_QUERY_GENERATION,
	build_task_prompt,
	heuristic_query_generation,
	normalize_task_result,
)


class TaskState(TypedDict, total=False):
	metadata: dict[str, Any]
	payload_messages: list[dict[str, Any]]
	task_kind: str
	prompt: str
	result: str


def _task_messages(state: TaskState) -> list[dict[str, Any]]:
	metadata = state.get("metadata") or {}
	payload_messages = state.get("payload_messages") or []
	task_body = metadata.get("task_body")
	if isinstance(task_body, dict) and isinstance(task_body.get("messages"), list):
		return task_body["messages"]
	return payload_messages


def _prepare_task_node(state: TaskState) -> dict[str, Any]:
	task_kind = str(state.get("task_kind") or "")
	messages = _task_messages(state)
	metadata = state.get("metadata") or {}
	prompt = build_task_prompt(task_kind, messages, metadata)
	if prompt is None:
		raise ValueError(f"unsupported task kind: {task_kind}")
	return {"prompt": prompt}


def _llm_once_node(
	llm_callable: Callable[[list[BaseMessage]], str],
) -> Callable[[TaskState], dict[str, Any]]:
	def node(state: TaskState) -> dict[str, Any]:
		prompt = state.get("prompt") or ""
		result = llm_callable([HumanMessage(content=prompt)])
		task_kind = str(state.get("task_kind") or "")
		return {"result": normalize_task_result(task_kind, result or "")}

	return node


def _finalize_task_node(state: TaskState) -> dict[str, Any]:
	return {"result": (state.get("result") or "").strip()}


def build_task_graph(
	llm_callable: Callable[[list[BaseMessage]], str],
	config: AgentConfig | None = None,
) -> Any:
	del config  # task profile applied via llm_registry["task"]
	graph = StateGraph(TaskState)
	graph.add_node("prepare_task", _prepare_task_node)
	graph.add_node("llm_once", _llm_once_node(llm_callable))
	graph.add_node("finalize_task", _finalize_task_node)
	graph.add_edge(START, "prepare_task")
	graph.add_edge("prepare_task", "llm_once")
	graph.add_edge("llm_once", "finalize_task")
	graph.add_edge("finalize_task", END)
	return graph.compile()


def run_task_completion(
	payload: dict[str, Any],
	metadata: dict[str, Any],
	llm_callable: Callable[[list[BaseMessage]], str],
	config: AgentConfig | None = None,
) -> str:
	task_kind = str(metadata.get("task") or "")
	if task_kind == TASK_QUERY_GENERATION:
		messages = _task_messages(
			{
				"metadata": metadata,
				"payload_messages": payload.get("messages") or [],
			}
		)
		return heuristic_query_generation(messages)

	if task_kind not in SUPPORTED_TASK_KINDS:
		messages = payload.get("messages")
		if isinstance(messages, list) and messages:
			last = messages[-1]
			if isinstance(last, dict) and last.get("content"):
				return str(last.get("content"))
		return ""

	compiled = build_task_graph(llm_callable, config=config)
	result = compiled.invoke(
		{
			"metadata": metadata,
			"payload_messages": payload.get("messages") or [],
			"task_kind": task_kind,
		}
	)
	return str(result.get("result") or "").strip()
