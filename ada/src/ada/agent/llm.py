from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ada.llm import ChatCompletionResult, ChatMessage, LLMClient, MessageContent, make_client
from ada.registry import Profile, get_profile, load_registry


def _to_message_content(message: BaseMessage) -> MessageContent:
	content = message.content
	if isinstance(content, list):
		return content
	return content if isinstance(content, str) else str(content)


def _to_chat_messages(messages: list[BaseMessage]) -> list[ChatMessage]:
	out: list[ChatMessage] = []
	for message in messages:
		if isinstance(message, HumanMessage):
			out.append(ChatMessage(role="user", content=_to_message_content(message)))
		elif isinstance(message, AIMessage):
			out.append(ChatMessage(role="assistant", content=_to_message_content(message)))
		elif isinstance(message, SystemMessage):
			out.append(ChatMessage(role="system", content=_to_message_content(message)))
	return out


def make_llm_callable(
	profile: Profile,
	vault_password: str | None = None,
	client_factory: Callable[[Profile], LLMClient] | None = None,
) -> Callable[[list[BaseMessage]], str]:
	if client_factory is None:
		client_factory = lambda p: make_client(p, vault_password=vault_password)
	client = client_factory(profile)

	def call_llm(messages: list[BaseMessage]) -> str:
		return client.chat(_to_chat_messages(messages))

	return call_llm


def make_tool_llm_callable(
	profile: Profile,
	vault_password: str | None = None,
	client_factory: Callable[[Profile], LLMClient] | None = None,
) -> Callable[[list[ChatMessage], list[dict[str, Any]] | None], ChatCompletionResult]:
	if client_factory is None:
		client_factory = lambda p: make_client(p, vault_password=vault_password)
	client = client_factory(profile)

	def call_with_tools(
		messages: list[ChatMessage],
		tools: list[dict[str, Any]] | None,
	) -> ChatCompletionResult:
		return client.chat_completion(messages, tools=tools)

	return call_with_tools


def load_profile_from_env() -> Profile:
	profile_name = os.environ.get("ADA_AGENT_PROFILE", "chat_profile")
	registry_path = os.environ.get("ADA_MODEL_REGISTRY")
	reg = load_registry(Path(registry_path)) if registry_path else load_registry()
	return get_profile(reg, profile_name)
