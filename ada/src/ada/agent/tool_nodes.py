from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ada.agent.config import AgentConfig
from ada.agent.tool_state import ToolAgentState
from ada.llm import ChatCompletionResult, ChatMessage


def _openai_messages_to_chat(messages: list[dict[str, Any]]) -> list[ChatMessage]:
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


def make_prepare_node(cfg: AgentConfig):
	def prepare_node(state: ToolAgentState) -> dict[str, Any]:
		messages = list(state.get("openai_messages") or [])
		if not messages:
			return {"done": True, "finish_reason": "stop", "assistant_message": {"role": "assistant", "content": ""}}
		if messages[0].get("role") != "system" and cfg.system_prompt.strip():
			messages = [{"role": "system", "content": cfg.system_prompt.strip()}, *messages]
		return {"openai_messages": messages, "tool_rounds": state.get("tool_rounds") or 0}

	return prepare_node


def make_tool_loop_node(
	cfg: AgentConfig,
	tool_llm_callable: Callable[[list[ChatMessage], list[dict[str, Any]] | None], ChatCompletionResult],
):
	def tool_loop_node(state: ToolAgentState) -> dict[str, Any]:
		messages = state.get("openai_messages") or []
		tools = state.get("tools") or []
		result = tool_llm_callable(_openai_messages_to_chat(messages), tools or None)
		assistant = _assistant_payload(result)
		updated = [*messages, assistant]
		return {
			"openai_messages": updated,
			"assistant_message": assistant,
			"finish_reason": result.finish_reason,
			"done": not result.tool_calls,
		}

	return tool_loop_node


def _execute_local_tool(name: str, arguments: str) -> str:
	if name == "noop":
		return json.dumps({"ok": True, "args": json.loads(arguments or "{}")})
	return json.dumps({"error": f"unknown tool: {name}"})


def make_execute_tool_node(cfg: AgentConfig):
	def execute_tool_node(state: ToolAgentState) -> dict[str, Any]:
		messages = list(state.get("openai_messages") or [])
		if not messages:
			return {"done": True}
		last = messages[-1]
		tool_calls = last.get("tool_calls")
		if not isinstance(tool_calls, list) or not tool_calls:
			return {"done": True}

		tool_messages: list[dict[str, Any]] = []
		for call in tool_calls:
			if not isinstance(call, dict):
				continue
			function = call.get("function") or {}
			name = str(function.get("name") or "")
			arguments = str(function.get("arguments") or "{}")
			call_id = str(call.get("id") or "")
			result = _execute_local_tool(name, arguments)
			tool_messages.append(
				{
					"role": "tool",
					"tool_call_id": call_id,
					"name": name,
					"content": result,
				}
			)

		rounds = int(state.get("tool_rounds") or 0) + 1
		return {
			"openai_messages": [*messages, *tool_messages],
			"tool_rounds": rounds,
			"done": False,
		}

	return execute_tool_node


def make_finalize_node(cfg: AgentConfig):
	def finalize_node(state: ToolAgentState) -> dict[str, Any]:
		assistant = state.get("assistant_message") or {"role": "assistant", "content": ""}
		return {
			"assistant_message": assistant,
			"finish_reason": state.get("finish_reason") or "stop",
			"done": True,
		}

	return finalize_node


def tool_loop_decision(state: ToolAgentState) -> str:
	if state.get("done"):
		return "finalize"
	rounds = int(state.get("tool_rounds") or 0)
	max_rounds = 10
	assistant = state.get("assistant_message") or {}
	if assistant.get("tool_calls") and rounds < max_rounds:
		return "execute"
	return "finalize"
