from __future__ import annotations

import json
import os
from typing import Any

import httpx

from ada.eval.harness.config import eval_base_url, load_eval_config
from ada.registry import get_profile, load_registry


class AgentEvalClient:
	"""OpenAI-compatible client targeting Ada Agent API."""

	def __init__(self, base_url: str | None = None, api_key: str = "local") -> None:
		self.base_url = (base_url or eval_base_url()).rstrip("/")
		self.api_key = api_key
		cfg = load_eval_config()
		profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
		self.model = get_profile(load_registry(), profile_name).model
		self._client = httpx.Client(timeout=float(os.environ.get("ADA_LLM_TIMEOUT", "300")))

	def chat(
		self,
		messages: list[dict[str, Any]],
		*,
		tools: list[dict[str, Any]] | None = None,
		tool_choice: str | dict[str, Any] | None = None,
		model: str | None = None,
	) -> dict[str, Any]:
		body: dict[str, Any] = {
			"model": model or self.model,
			"messages": messages,
			"stream": False,
		}
		if tools:
			body["tools"] = tools
		if tool_choice is not None:
			body["tool_choice"] = tool_choice
		resp = self._client.post(
			f"{self.base_url}/chat/completions",
			headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
			json=body,
		)
		resp.raise_for_status()
		return resp.json()

	def close(self) -> None:
		self._client.close()

	def __enter__(self) -> AgentEvalClient:
		return self

	def __exit__(self, *args: object) -> None:
		self.close()


def chat_completion(
	messages: list[dict[str, Any]],
	*,
	tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	with AgentEvalClient() as client:
		return client.chat(messages, tools=tools)
