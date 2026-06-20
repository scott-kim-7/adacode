from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ada.agent.config import AgentConfig
from ada.agent.content import extract_text_from_content
from ada.agent.jwt_context import get_request_jwt
from ada.agent.nodes import _latest_user_text
from ada.agent.unified_state import UnifiedAgentState
from ada.memory.factory import get_memory_backend
from ada.memory.owui_backend import format_memory_context
from ada.owui_adapt.rag import DEFAULT_RAG_TEMPLATE, rag_template, sources_to_context_string
from ada.retrieve.factory import get_retrieval_backend
from ada.search.service import run_search_batch
from ada.tools.owui_backend import OwuiToolBackend
from ada.vault import VaultSession


def _feature_enabled(metadata: dict[str, Any], name: str) -> bool:
	features = metadata.get("features")
	if not isinstance(features, dict):
		return False
	return bool(features.get(name))


def make_memory_gate_node(
	memory_backend=None,
) -> Callable[[UnifiedAgentState], dict[str, Any]]:
	backend = memory_backend or get_memory_backend()

	def memory_gate(state: UnifiedAgentState) -> dict[str, Any]:
		metadata = state.get("metadata") or {}
		if not _feature_enabled(metadata, "memory"):
			return {}
		user_text = _latest_user_text(state.get("messages") or [])
		if not user_text:
			return {}
		jwt = get_request_jwt()

		async def _run() -> str:
			result = await backend.query(user_text, k=3, jwt=jwt)
			return format_memory_context(result)

		memory_context = asyncio.run(_run())
		if not memory_context:
			return {}
		return {
			"memory_context": memory_context,
			"messages": [SystemMessage(content=memory_context)],
		}

	return memory_gate


def make_search_gate_node() -> Callable[[UnifiedAgentState], dict[str, Any]]:
	def search_gate(state: UnifiedAgentState) -> dict[str, Any]:
		metadata = state.get("metadata") or {}
		if not _feature_enabled(metadata, "web_search"):
			return {"search_items": []}
		return {}

	return search_gate


def search_gate_decision(state: UnifiedAgentState) -> str:
	metadata = state.get("metadata") or {}
	if _feature_enabled(metadata, "web_search"):
		return "search_batch"
	return "retrieve_gate"


def make_search_batch_node(
	vault_session: VaultSession | None = None,
) -> Callable[[UnifiedAgentState], dict[str, Any]]:
	def search_batch(state: UnifiedAgentState) -> dict[str, Any]:
		user_text = _latest_user_text(state.get("messages") or [])
		if not user_text:
			return {"search_items": []}
		items = run_search_batch(user_text, vault_session=vault_session)
		return {"search_items": items}

	return search_batch


def make_retrieve_gate_node() -> Callable[[UnifiedAgentState], dict[str, Any]]:
	def retrieve_gate(state: UnifiedAgentState) -> dict[str, Any]:
		metadata = state.get("metadata") or {}
		files = metadata.get("files")
		search_items = state.get("search_items") or []
		if (isinstance(files, list) and files) or search_items:
			return {}
		return {"retrieve_sources": []}

	return retrieve_gate


def retrieve_gate_decision(state: UnifiedAgentState) -> str:
	metadata = state.get("metadata") or {}
	files = metadata.get("files")
	search_items = state.get("search_items") or []
	if (isinstance(files, list) and files) or search_items:
		return "retrieve"
	return "inject_context"


def make_retrieve_node(
	retrieval_backend=None,
) -> Callable[[UnifiedAgentState], dict[str, Any]]:
	backend = retrieval_backend or get_retrieval_backend()

	def retrieve(state: UnifiedAgentState) -> dict[str, Any]:
		metadata = state.get("metadata") or {}
		user_text = _latest_user_text(state.get("messages") or [])
		if not user_text:
			return {"retrieve_sources": []}
		files = metadata.get("files") if isinstance(metadata.get("files"), list) else []
		items = [*files, *(state.get("search_items") or [])]
		if not items:
			return {"retrieve_sources": []}
		jwt = get_request_jwt()

		async def _run() -> list[dict[str, Any]]:
			return await backend.fetch_sources(items, [user_text], jwt=jwt)

		sources = asyncio.run(_run())
		return {"retrieve_sources": sources}

	return retrieve


def make_inject_context_node() -> Callable[[UnifiedAgentState], dict[str, Any]]:
	def inject_context(state: UnifiedAgentState) -> dict[str, Any]:
		sources = state.get("retrieve_sources") or []
		if not sources:
			return {}
		context_string = sources_to_context_string(sources)
		if not context_string:
			return {}
		user_text = _latest_user_text(state.get("messages") or [])
		prompt = rag_template(DEFAULT_RAG_TEMPLATE, context_string, user_text)
		messages = list(state.get("messages") or [])
		updated: list[Any] = []
		replaced = False
		for message in reversed(messages):
			if not replaced and isinstance(message, HumanMessage):
				updated.insert(0, HumanMessage(content=prompt))
				replaced = True
			else:
				updated.insert(0, message)
		if not replaced:
			updated.append(HumanMessage(content=prompt))
		return {"messages": updated}

	return inject_context


def tool_gate_decision(state: UnifiedAgentState) -> str:
	if state.get("use_tool_branch"):
		return "tool_loop"
	return "route"


def make_tool_loop_node(
	tool_llm_callable: Callable[..., Any],
) -> Callable[[UnifiedAgentState], dict[str, Any]]:
	from ada.agent.tool_graph import run_tool_agent_turn

	def tool_loop(state: UnifiedAgentState) -> dict[str, Any]:
		tools = state.get("openai_tools") or []
		messages = list(state.get("openai_messages") or [])
		if not messages:
			assistant = {"role": "assistant", "content": ""}
			return {
				"tool_assistant": assistant,
				"assistant_message": assistant,
				"tool_finish_reason": "stop",
				"tool_done": True,
			}
		assistant, finish_reason = run_tool_agent_turn(
			messages,
			tools,
			tool_llm_callable,
			auto_execute=False,
		)
		has_tool_calls = bool(assistant.get("tool_calls"))
		return {
			"openai_messages": [*messages, assistant],
			"tool_assistant": assistant,
			"assistant_message": assistant,
			"tool_finish_reason": finish_reason,
			"tool_done": not has_tool_calls,
		}

	return tool_loop


def make_owui_execute_tool_node(
	tool_backend: OwuiToolBackend | None = None,
) -> Callable[[UnifiedAgentState], dict[str, Any]]:
	backend = tool_backend or OwuiToolBackend()

	def execute_tool(state: UnifiedAgentState) -> dict[str, Any]:
		messages = list(state.get("openai_messages") or [])
		if not messages:
			return {"tool_done": True}
		last = messages[-1]
		tool_calls = last.get("tool_calls")
		if not isinstance(tool_calls, list) or not tool_calls:
			return {"tool_done": True}

		metadata = state.get("metadata") or {}
		tool_ids = metadata.get("tool_ids") if isinstance(metadata.get("tool_ids"), list) else []
		jwt = get_request_jwt()

		tool_messages: list[dict[str, Any]] = []

		async def _run() -> list[dict[str, Any]]:
			out: list[dict[str, Any]] = []
			for call in tool_calls:
				if not isinstance(call, dict):
					continue
				function = call.get("function") or {}
				name = str(function.get("name") or "")
				arguments = str(function.get("arguments") or "{}")
				call_id = str(call.get("id") or "")
				content = await backend.execute(name, arguments, tool_ids, jwt)
				out.append(
					{
						"role": "tool",
						"tool_call_id": call_id,
						"name": name,
						"content": content,
					}
				)
			return out

		tool_messages = asyncio.run(_run())
		rounds = int(state.get("tool_rounds") or 0) + 1
		return {
			"openai_messages": [*messages, *tool_messages],
			"tool_rounds": rounds,
			"tool_done": False,
		}

	return execute_tool


def unified_tool_loop_decision(state: UnifiedAgentState) -> str:
	if state.get("tool_done"):
		return "tool_finalize"
	rounds = int(state.get("tool_rounds") or 0)
	if rounds >= 10:
		return "tool_finalize"
	assistant = state.get("assistant_message") or {}
	if assistant.get("tool_calls"):
		return "execute_tool"
	return "tool_finalize"


def make_tool_finalize_node() -> Callable[[UnifiedAgentState], dict[str, Any]]:
	def tool_finalize(state: UnifiedAgentState) -> dict[str, Any]:
		assistant = state.get("assistant_message") or state.get("tool_assistant") or {
			"role": "assistant",
			"content": "",
		}
		return {
			"tool_assistant": assistant,
			"tool_finish_reason": state.get("tool_finish_reason") or "stop",
			"tool_done": True,
		}

	return tool_finalize
