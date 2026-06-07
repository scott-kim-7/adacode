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


DEFAULT_SYSTEM_PROMPT = "You are Ada, a helpful assistant."


@dataclass(frozen=True)
class AgentConfig:
	system_prompt: str = DEFAULT_SYSTEM_PROMPT
	routing: RoutingConfig = field(default_factory=RoutingConfig)
	plan: PlanConfig = field(default_factory=PlanConfig)
	respond: RespondConfig = field(default_factory=RespondConfig)
	verify: VerifyConfig = field(default_factory=VerifyConfig)


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
	)
