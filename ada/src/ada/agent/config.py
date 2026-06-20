from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ada.paths import ada_root


@dataclass(frozen=True)
class RoutingConfig:
	plan_min_chars: int = 180
	plan_keywords: tuple[str, ...] = ("plan", "step by step", "design", "계획", "설계")


@dataclass(frozen=True)
class PlanConfig:
	enabled: bool = True
	prompt: str = "Create a short internal plan (3-5 bullet points) for answering the user."


@dataclass(frozen=True)
class RespondConfig:
	include_plan_hint: bool = True


@dataclass(frozen=True)
class VerifyConfig:
	max_empty_retries: int = 1


@dataclass(frozen=True)
class VisionConfig:
	image_only_prompt: str = "Describe the image."


@dataclass(frozen=True)
class ToolsConfig:
	max_rounds: int = 10
	timeout_sec: int = 300


@dataclass(frozen=True)
class StreamConfig:
	# ChatGPT-style inline collapsible thinking in the same message bubble (content SSE).
	inline_thinking: bool = True
	expose_graph_trace: bool = True
	trace_direct_route: bool = True
	# Legacy alias for inline_thinking (yaml key plan_fallback_tags).
	plan_fallback_tags: bool = True


DEFAULT_SYSTEM_PROMPT = "You are Ada, a helpful assistant."

DEFAULT_CHAT_BASE_URL = "http://127.0.0.1:8089/v1"
DEFAULT_TASK_MODEL_ID = "mlx-coder"


@dataclass(frozen=True)
class ModelEndpointConfig:
	base_url: str
	model_id: str = ""
	api_key: str = "local"
	max_tokens: int | None = None


@dataclass(frozen=True)
class ModelsConfig:
	chat: ModelEndpointConfig
	task: ModelEndpointConfig
	tool_alias: str = "chat"


def default_models_config() -> ModelsConfig:
	endpoint = ModelEndpointConfig(
		base_url=DEFAULT_CHAT_BASE_URL,
		model_id=DEFAULT_TASK_MODEL_ID,
		api_key="local",
	)
	task = ModelEndpointConfig(
		base_url=DEFAULT_CHAT_BASE_URL,
		model_id=DEFAULT_TASK_MODEL_ID,
		api_key="local",
		max_tokens=512,
	)
	return ModelsConfig(chat=endpoint, task=task, tool_alias="chat")


@dataclass(frozen=True)
class AgentConfig:
	system_prompt: str = DEFAULT_SYSTEM_PROMPT
	routing: RoutingConfig = field(default_factory=RoutingConfig)
	plan: PlanConfig = field(default_factory=PlanConfig)
	respond: RespondConfig = field(default_factory=RespondConfig)
	verify: VerifyConfig = field(default_factory=VerifyConfig)
	vision: VisionConfig = field(default_factory=VisionConfig)
	tools: ToolsConfig = field(default_factory=ToolsConfig)
	stream: StreamConfig = field(default_factory=StreamConfig)
	models: ModelsConfig = field(default_factory=default_models_config)


def _as_tuple(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
	if not isinstance(value, list):
		return default
	return tuple(str(item) for item in value if str(item).strip())


def load_agent_config(path: Path | None = None) -> AgentConfig:
	config_path = path or ada_root() / "config" / "agent.yaml"
	if not config_path.is_file():
		return AgentConfig()

	raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
	if not isinstance(raw, dict):
		return AgentConfig()

	routing_raw = raw.get("routing") or {}
	plan_raw = raw.get("plan") or {}
	respond_raw = raw.get("respond") or {}
	verify_raw = raw.get("verify") or {}
	vision_raw = raw.get("vision") or {}
	tools_raw = raw.get("tools") or {}
	stream_raw = raw.get("stream") or {}
	models_raw = raw.get("models") or {}

	def _parse_endpoint(name: str, data: object) -> ModelEndpointConfig:
		defaults = default_models_config()
		base = defaults.chat if name == "chat" else defaults.task
		if not isinstance(data, dict):
			return base
		max_tokens_raw = data.get("max_tokens")
		max_tokens = int(max_tokens_raw) if max_tokens_raw is not None else base.max_tokens
		return ModelEndpointConfig(
			base_url=str(data.get("base_url") or base.base_url).rstrip("/"),
			model_id=str(data.get("model_id") if data.get("model_id") is not None else base.model_id),
			api_key=str(data.get("api_key") or base.api_key),
			max_tokens=max_tokens,
		)

	models = ModelsConfig(
		chat=_parse_endpoint("chat", models_raw.get("chat")),
		task=_parse_endpoint("task", models_raw.get("task")),
		tool_alias=str(models_raw.get("tool") or "chat"),
	)

	return AgentConfig(
		system_prompt=str(raw.get("system_prompt") or DEFAULT_SYSTEM_PROMPT).strip(),
		routing=RoutingConfig(
			plan_min_chars=int(routing_raw.get("plan_min_chars") or 180),
			plan_keywords=_as_tuple(
				routing_raw.get("plan_keywords"),
				RoutingConfig().plan_keywords,
			),
		),
		plan=PlanConfig(
			enabled=bool(plan_raw.get("enabled", True)),
			prompt=str(plan_raw.get("prompt") or PlanConfig().prompt).strip(),
		),
		respond=RespondConfig(
			include_plan_hint=bool(respond_raw.get("include_plan_hint", True)),
		),
		verify=VerifyConfig(
			max_empty_retries=int(verify_raw.get("max_empty_retries") or 1),
		),
		vision=VisionConfig(
			image_only_prompt=str(
				vision_raw.get("image_only_prompt") or VisionConfig().image_only_prompt
			).strip(),
		),
		tools=ToolsConfig(
			max_rounds=int(tools_raw.get("max_rounds") or 10),
			timeout_sec=int(tools_raw.get("timeout_sec") or 300),
		),
		stream=StreamConfig(
			inline_thinking=bool(
				stream_raw.get(
					"inline_thinking",
					stream_raw.get("plan_fallback_tags", True),
				)
			),
			expose_graph_trace=bool(stream_raw.get("expose_graph_trace", True)),
			trace_direct_route=bool(stream_raw.get("trace_direct_route", True)),
			plan_fallback_tags=bool(
				stream_raw.get(
					"plan_fallback_tags",
					stream_raw.get("inline_thinking", True),
				)
			),
		),
		models=models,
	)
