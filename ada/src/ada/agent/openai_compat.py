from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ada.agent.config import AgentConfig, load_agent_config
from ada.agent.graph import build_simple_agent_graph, run_user_turn


def _message_content(raw: Any) -> str:
	if raw is None:
		return ""
	if isinstance(raw, str):
		return raw
	if isinstance(raw, list):
		parts: list[str] = []
		for item in raw:
			if not isinstance(item, dict):
				parts.append(str(item))
				continue
			if item.get("type") == "text":
				parts.append(str(item.get("text") or ""))
			elif "text" in item:
				parts.append(str(item["text"]))
		return "\n".join(part for part in parts if part)
	return str(raw)


def openai_messages_to_langchain(messages: list[dict[str, Any]]) -> list[BaseMessage]:
	out: list[BaseMessage] = []
	for message in messages:
		if not isinstance(message, dict):
			continue
		role = str(message.get("role") or "user")
		content = _message_content(message.get("content"))
		if role == "system":
			out.append(SystemMessage(content=content))
		elif role == "assistant":
			out.append(AIMessage(content=content))
		else:
			out.append(HumanMessage(content=content))
	return out


def split_history_and_user(messages: list[dict[str, Any]]) -> tuple[list[BaseMessage], str]:
	converted = openai_messages_to_langchain(messages)
	if not converted:
		return [], ""
	if isinstance(converted[-1], HumanMessage):
		last = converted[-1]
		content = last.content if isinstance(last.content, str) else str(last.content)
		return converted[:-1], content.strip()
	return converted, ""


def run_chat_completion(
	messages: list[dict[str, Any]],
	llm_callable: Callable[[list[BaseMessage]], str],
	config: AgentConfig | None = None,
) -> str:
	cfg = config or load_agent_config()
	history, user_text = split_history_and_user(messages)
	if user_text:
		assistant_text, _ = run_user_turn(user_text, history, llm_callable, config=cfg)
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
