from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
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
from ada.agent.stream_sink import StreamChunk, StreamContext, StreamSink


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
	stream_context: StreamContext | None = None,
) -> str:
	from ada.agent.graph import build_simple_agent_graph, run_user_turn

	cfg = config or load_agent_config()
	history, user_content = split_history_and_user(messages)
	if not content_is_empty(user_content):
		assistant_text, _ = run_user_turn(
			user_content,
			history,
			llm_callable,
			config=cfg,
			stream_context=stream_context,
		)
		return assistant_text
	converted = openai_messages_to_langchain(messages)
	if not converted:
		return ""
	run_turn = build_simple_agent_graph(
		llm_callable,
		config=cfg,
		stream_context=stream_context,
	)
	return run_turn(converted)


def run_chat_completion_streaming(
	messages: list[dict[str, Any]],
	llm_callable: Callable[[list[BaseMessage]], str],
	stream_sink: StreamSink,
	config: AgentConfig | None = None,
	stream_context: StreamContext | None = None,
) -> str:
	"""Run MainGraph; llm_callable and graph must share the same StreamContext."""
	try:
		result = run_chat_completion(
			messages,
			llm_callable,
			config=config,
			stream_context=stream_context,
		)
	except BaseException as exc:
		stream_sink.finish(error=exc)
		raise
	stream_sink.finish()
	return result


def _sse_line(payload: dict[str, Any]) -> str:
	return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


def build_chat_completion_chunk(
	model: str,
	completion_id: str,
	created: int,
	*,
	delta: dict[str, Any],
	finish_reason: str | None = None,
) -> dict[str, Any]:
	return {
		"id": completion_id,
		"object": "chat.completion.chunk",
		"created": created,
		"model": model,
		"choices": [
			{
				"index": 0,
				"delta": delta,
				"finish_reason": finish_reason,
			}
		],
	}


async def iter_sse_chat_completion(
	sink: StreamSink,
	model: str,
	*,
	run_turn: Callable[[], str],
	include_usage: bool = False,
) -> AsyncIterator[str]:
	completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
	created = int(time.time())
	loop = asyncio.get_running_loop()
	task = asyncio.create_task(asyncio.to_thread(run_turn))
	sent_role = False

	try:
		while True:
			item = await loop.run_in_executor(None, sink.get)
			if isinstance(item, BaseException):
				message = str(item) or item.__class__.__name__
				yield _sse_line(
					build_chat_completion_chunk(
						model,
						completion_id,
						created,
						delta={"content": f"\n\n[error] {message}\n"},
					)
				)
				yield _sse_line(
					build_chat_completion_chunk(
						model,
						completion_id,
						created,
						delta={},
						finish_reason="stop",
					)
				)
				yield "data: [DONE]\n\n"
				break
			if item is None:
				if include_usage:
					yield _sse_line(
						{
							"id": completion_id,
							"object": "chat.completion.chunk",
							"created": created,
							"model": model,
							"choices": [],
							"usage": {
								"prompt_tokens": 0,
								"completion_tokens": 0,
								"total_tokens": 0,
							},
						}
					)
				yield _sse_line(
					build_chat_completion_chunk(
						model,
						completion_id,
						created,
						delta={},
						finish_reason="stop",
					)
				)
				yield "data: [DONE]\n\n"
				break
			if not isinstance(item, StreamChunk):
				continue
			delta: dict[str, Any] = {}
			if item.channel == "reasoning":
				delta["reasoning_content"] = item.text
			else:
				delta["content"] = item.text
			if not sent_role:
				delta["role"] = "assistant"
				sent_role = True
			yield _sse_line(
				build_chat_completion_chunk(model, completion_id, created, delta=delta)
			)
	finally:
		# Do not let background thread errors truncate an already-finished SSE body.
		try:
			await task
		except BaseException:
			pass


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
