from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ada.agent.config import AgentConfig, ModelEndpointConfig, ModelsConfig
from ada.agent.llm import make_llm_callable, make_tool_llm_callable
from ada.agent.stream_sink import StreamContext
from ada.llm import ChatCompletionResult
from ada.openai_models import effective_model_id
from ada.registry import Profile
from ada.vault import VaultSession


def profile_from_endpoint(
	name: str,
	endpoint: ModelEndpointConfig,
	*,
	tool_calling: bool = False,
) -> Profile:
	return Profile(
		name=name,
		label=name,
		provider="openai-compatible",
		base_url=endpoint.base_url.rstrip("/"),
		api_key=endpoint.api_key,
		tool_calling=tool_calling,
		model_id=endpoint.model_id,
		max_tokens=endpoint.max_tokens,
	)


def build_llm_registry(
	cfg: AgentConfig,
	vault_session: VaultSession | None = None,
	stream_context: StreamContext | None = None,
) -> dict[str, Any]:
	chat_profile = profile_from_endpoint("chat", cfg.models.chat, tool_calling=True)
	task_profile = profile_from_endpoint("task", cfg.models.task, tool_calling=False)
	return {
		"chat": make_llm_callable(
			chat_profile,
			vault_session=vault_session,
			stream_context=stream_context,
		),
		"task": make_llm_callable(task_profile, vault_session=vault_session),
		"tool": make_tool_llm_callable(chat_profile, vault_session=vault_session),
	}


def resolve_task_model_id(cfg: AgentConfig) -> str:
	model_id = (cfg.models.task.model_id or "").strip()
	return model_id or "mlx-coder"


def _effective_model_for_endpoint(
	endpoint: ModelEndpointConfig,
	requested: str | None = None,
) -> str:
	preferred = (endpoint.model_id or "").strip() or None
	fallback = (requested or "").strip() or None
	return effective_model_id(
		endpoint.base_url.rstrip("/"),
		preferred or fallback,
		api_key=endpoint.api_key or "local",
	)


def resolve_effective_chat_model_id(cfg: AgentConfig, *, requested: str = "") -> str:
	return _effective_model_for_endpoint(cfg.models.chat, requested=requested)


def resolve_effective_task_model_id(cfg: AgentConfig) -> str:
	return _effective_model_for_endpoint(cfg.models.task)


def models_config_to_api(cfg: ModelsConfig) -> dict[str, Any]:
	return {
		"chat": {
			"base_url": cfg.chat.base_url,
			"model_id": cfg.chat.model_id,
			"api_key": cfg.chat.api_key,
		},
		"task": {
			"base_url": cfg.task.base_url,
			"model_id": cfg.task.model_id,
			"api_key": cfg.task.api_key,
			"max_tokens": cfg.task.max_tokens,
		},
		"tool": cfg.tool_alias,
	}


def models_config_from_api(raw: dict[str, Any], current: ModelsConfig) -> ModelsConfig:
	chat_raw = raw.get("chat") if isinstance(raw.get("chat"), dict) else {}
	task_raw = raw.get("task") if isinstance(raw.get("task"), dict) else {}
	max_tokens = task_raw.get("max_tokens", current.task.max_tokens)
	return ModelsConfig(
		chat=ModelEndpointConfig(
			base_url=str(chat_raw.get("base_url") or current.chat.base_url).rstrip("/"),
			model_id=str(chat_raw.get("model_id") if chat_raw.get("model_id") is not None else current.chat.model_id),
			api_key=str(chat_raw.get("api_key") or current.chat.api_key),
		),
		task=ModelEndpointConfig(
			base_url=str(task_raw.get("base_url") or current.task.base_url).rstrip("/"),
			model_id=str(task_raw.get("model_id") if task_raw.get("model_id") is not None else current.task.model_id),
			api_key=str(task_raw.get("api_key") or current.task.api_key),
			max_tokens=int(max_tokens) if max_tokens is not None else current.task.max_tokens,
		),
		tool_alias=str(raw.get("tool") or current.tool_alias),
	)
