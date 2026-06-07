from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ada.llm import ChatMessage, LLMClient, make_client
from ada.registry import Profile, get_profile, load_registry


def _to_chat_messages(messages: list[BaseMessage]) -> list[ChatMessage]:
	out: list[ChatMessage] = []
	for message in messages:
		if isinstance(message, HumanMessage):
			content = message.content if isinstance(message.content, str) else str(message.content)
			out.append(ChatMessage(role="user", content=content))
		elif isinstance(message, AIMessage):
			content = message.content if isinstance(message.content, str) else str(message.content)
			out.append(ChatMessage(role="assistant", content=content))
		elif isinstance(message, SystemMessage):
			content = message.content if isinstance(message.content, str) else str(message.content)
			out.append(ChatMessage(role="system", content=content))
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


def load_profile_from_env() -> Profile:
	profile_name = os.environ.get("ADA_AGENT_PROFILE", "chat_profile")
	registry_path = os.environ.get("ADA_MODEL_REGISTRY")
	reg = load_registry(Path(registry_path)) if registry_path else load_registry()
	return get_profile(reg, profile_name)
