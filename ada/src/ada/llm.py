from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from ada.openai_stream import (
	content_delta_from_chunk,
	finish_reason_from_chunk,
	is_sse_done_line,
	parse_sse_data_line,
)
from ada.registry import Profile
from ada.vault import Vault, VaultError, prompt_password

MessageContent = str | list[dict[str, Any]]


@dataclass(frozen=True)
class ChatMessage:
	role: str
	content: MessageContent | None = None
	tool_calls: tuple[dict[str, Any], ...] | None = None
	tool_call_id: str | None = None
	name: str | None = None
	speaker: str = ""


@dataclass(frozen=True)
class ChatCompletionResult:
	content: str | None
	tool_calls: list[dict[str, Any]] | None
	finish_reason: str


class LLMClient:
	def __init__(self, profile: Profile, api_key: str | None = None) -> None:
		self.profile = profile
		self.api_key = api_key or profile.api_key or "local"
		timeout = float(os.environ.get("ADA_LLM_TIMEOUT", "300"))
		self._client = httpx.Client(timeout=timeout)
		self._model_id: str | None = None

	def _model(self) -> str:
		if self._model_id is None:
			from ada.openai_models import effective_model_id

			self._model_id = effective_model_id(self.profile.base_url, None, api_key=self.api_key)
		return self._model_id

	def _serialize_message(self, message: ChatMessage) -> dict[str, Any]:
		payload: dict[str, Any] = {"role": message.role}
		if message.content is not None:
			payload["content"] = message.content
		if message.tool_calls:
			payload["tool_calls"] = list(message.tool_calls)
		if message.tool_call_id:
			payload["tool_call_id"] = message.tool_call_id
		if message.name:
			payload["name"] = message.name
		return payload

	def chat_completion(
		self,
		messages: list[ChatMessage],
		*,
		tools: list[dict[str, Any]] | None = None,
		tool_choice: str | dict[str, Any] | None = None,
		max_tokens: int = 1024,
	) -> ChatCompletionResult:
		payload_messages = [self._serialize_message(m) for m in messages]
		url = f"{self.profile.base_url.rstrip('/')}/chat/completions"
		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}
		body: dict[str, Any] = {
			"model": self._model(),
			"messages": payload_messages,
			"stream": False,
			"max_tokens": max_tokens,
		}
		if tools:
			body["tools"] = tools
		if tool_choice is not None:
			body["tool_choice"] = tool_choice
		resp = self._client.post(url, headers=headers, json=body)
		resp.raise_for_status()
		data = resp.json()
		choice = data["choices"][0]
		message = choice.get("message") or {}
		raw_tool_calls = message.get("tool_calls")
		tool_calls = list(raw_tool_calls) if isinstance(raw_tool_calls, list) else None
		content = message.get("content")
		text = None if content is None else str(content)
		return ChatCompletionResult(
			content=text,
			tool_calls=tool_calls,
			finish_reason=str(choice.get("finish_reason") or "stop"),
		)

	def chat(self, messages: list[ChatMessage], max_tokens: int = 1024) -> str:
		result = self.chat_completion(messages, max_tokens=max_tokens)
		return result.content or ""

	def chat_completion_stream(
		self,
		messages: list[ChatMessage],
		*,
		on_delta: Callable[[str], None],
		max_tokens: int = 1024,
	) -> ChatCompletionResult:
		payload_messages = [self._serialize_message(m) for m in messages]
		url = f"{self.profile.base_url.rstrip('/')}/chat/completions"
		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}
		body: dict[str, Any] = {
			"model": self._model(),
			"messages": payload_messages,
			"stream": True,
			"max_tokens": max_tokens,
		}
		text_parts: list[str] = []
		finish_reason = "stop"
		with self._client.stream("POST", url, headers=headers, json=body) as resp:
			resp.raise_for_status()
			for line in resp.iter_lines():
				if not line:
					continue
				if is_sse_done_line(line):
					break
				data = parse_sse_data_line(line)
				if data is None:
					continue
				reason = finish_reason_from_chunk(data)
				if reason:
					finish_reason = reason
				delta_text = content_delta_from_chunk(data)
				if delta_text:
					text_parts.append(delta_text)
					on_delta(delta_text)
				if reason:
					break
		content = "".join(text_parts)
		return ChatCompletionResult(
			content=content or None,
			tool_calls=None,
			finish_reason=finish_reason,
		)

	def close(self) -> None:
		self._client.close()


def resolve_api_key(profile: Profile, vault_password: str | None = None) -> str:
	if profile.api_key:
		return profile.api_key

	if profile.api_key_vault:
		env_key = profile.api_key_vault.upper().replace(".", "_")
		from_env = os.environ.get(f"ADA_{env_key}") or os.environ.get("ADA_EXTERNAL_API_KEY")
		if from_env:
			return from_env

		vault = Vault()
		if not vault.exists():
			raise VaultError(
				f"Profile '{profile.name}' needs vault key '{profile.api_key_vault}'. "
				f"Run: cd ada && make vault-init && make vault-set KEY={profile.api_key_vault}"
			)
		password = vault_password or prompt_password("VAULT_UNLOCK")
		value = vault.get(profile.api_key_vault, password)
		if not value:
			raise VaultError(
				f"Vault key '{profile.api_key_vault}' not set. "
				f"Run: make vault-set KEY={profile.api_key_vault}"
			)
		return value

	raise VaultError(f"Profile '{profile.name}' has no api_key or api_key_vault")


def make_client(profile: Profile, vault_password: str | None = None) -> LLMClient:
	api_key = resolve_api_key(profile, vault_password)
	return LLMClient(profile, api_key=api_key)
