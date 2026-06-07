from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ada.agent.config import AgentConfig, load_agent_config
from ada.agent.content import (
	UserContent,
	content_is_empty,
	ensure_user_prompt,
	extract_text_from_content,
	parse_openai_content,
)


def openai_messages_to_langchain(messages: list[dict[str, Any]]) -> list[BaseMessage]:
	out: list[BaseMessage] = []
	for message in messages:
		if not isinstance(message, dict):
			continue
		role = str(message.get("role") or "user")
		raw_content = message.get("content")
		if role == "system":
			out.append(SystemMessage(content=extract_text_from_content(parse_openai_content(raw_content))))
		elif role == "assistant":
			out.append(AIMessage(content=extract_text_from_content(parse_openai_content(raw_content))))
		else:
			out.append(HumanMessage(content=parse_openai_content(raw_content)))
	return out


def split_history_and_user(messages: list[dict[str, Any]]) -> tuple[list[BaseMessage], UserContent]:
	converted = openai_messages_to_langchain(messages)
	if not converted:
		return [], ""
	if isinstance(converted[-1], HumanMessage):
		last = converted[-1]
		user_content = last.content if isinstance(last.content, (str, list)) else str(last.content)
		return converted[:-1], user_content
	return converted, ""


def run_chat_completion(
	messages: list[dict[str, Any]],
	llm_callable: Callable[[list[BaseMessage]], str],
	config: AgentConfig | None = None,
) -> str:
	from ada.agent.graph import build_simple_agent_graph, run_user_turn

	cfg = config or load_agent_config()
	history, user_content = split_history_and_user(messages)
	if not content_is_empty(user_content):
		assistant_text, _ = run_user_turn(user_content, history, llm_callable, config=cfg)
		return assistant_text
	converted = openai_messages_to_langchain(messages)
	if not converted:
		return ""
	run_turn = build_simple_agent_graph(llm_callable, config=cfg)
	return run_turn(converted)


def build_chat_completion_response(model: str, content: str) -> dict[str, Any]:
	now = int(time.time())
	return {
		"id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
		"object": "chat.completion",
		"created": now,
		"model": model,
		"choices": [
			{
				"index": 0,
				"message": {"role": "assistant", "content": content},
				"finish_reason": "stop",
			}
		],
		"usage": {
			"prompt_tokens": 0,
			"completion_tokens": 0,
			"total_tokens": 0,
		},
	}


def build_tool_chat_completion_response(
	model: str,
	assistant_message: dict[str, Any],
	finish_reason: str,
) -> dict[str, Any]:
	now = int(time.time())
	message = {"role": "assistant", **assistant_message}
	if "role" in message and message["role"] != "assistant":
		message["role"] = "assistant"
	return {
		"id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
		"object": "chat.completion",
		"created": now,
		"model": model,
		"choices": [
			{
				"index": 0,
				"message": message,
				"finish_reason": finish_reason,
			}
		],
		"usage": {
			"prompt_tokens": 0,
			"completion_tokens": 0,
			"total_tokens": 0,
		},
	}


def run_tool_chat_completion(
	messages: list[dict[str, Any]],
	tools: list[dict[str, Any]],
	tool_llm_callable: Callable[..., Any],
	config: AgentConfig | None = None,
	*,
	tool_choice: str | dict[str, Any] | None = None,
	auto_execute: bool = False,
) -> tuple[dict[str, Any], str]:
	from ada.agent.tool_graph import run_tool_agent_turn

	del tool_choice  # reserved for future passthrough
	cfg = config or load_agent_config()
	assistant, finish_reason = run_tool_agent_turn(
		messages,
		tools,
		tool_llm_callable,
		config=cfg,
		auto_execute=auto_execute,
	)
	return assistant, finish_reason
