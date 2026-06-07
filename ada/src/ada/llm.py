from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from ada.registry import Profile
from ada.vault import Vault, VaultError, prompt_password

MessageContent = str | list[dict[str, Any]]


@dataclass(frozen=True)
class ChatMessage:
	role: str
	content: MessageContent
	speaker: str = ""


class LLMClient:
	def __init__(self, profile: Profile, api_key: str | None = None) -> None:
		self.profile = profile
		self.api_key = api_key or profile.api_key or "local"
		timeout = float(os.environ.get("ADA_LLM_TIMEOUT", "300"))
		self._client = httpx.Client(timeout=timeout)

	def chat(self, messages: list[ChatMessage], max_tokens: int = 1024) -> str:
		payload_messages = [
			{"role": m.role, "content": m.content}
			for m in messages
		]
		url = f"{self.profile.base_url.rstrip('/')}/chat/completions"
		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}
		body = {
			"model": self.profile.model,
			"messages": payload_messages,
			"stream": False,
			"max_tokens": max_tokens,
		}
		resp = self._client.post(url, headers=headers, json=body)
		resp.raise_for_status()
		data = resp.json()
		return str(data["choices"][0]["message"]["content"])

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
