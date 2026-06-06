from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ada.paths import registry_path


@dataclass(frozen=True)
class Profile:
	name: str
	label: str
	provider: str
	base_url: str
	model: str
	api_key: str | None = None
	api_key_vault: str | None = None
	tool_calling: bool = False
	notes: str = ""


@dataclass(frozen=True)
class TriChatConfig:
	turn_order: list[str]
	local_profile: str
	external_profile: str


@dataclass(frozen=True)
class ModelRegistry:
	profiles: dict[str, Profile]
	tri_chat: TriChatConfig


def _parse_profile(name: str, raw: dict[str, Any]) -> Profile:
	return Profile(
		name=name,
		label=str(raw.get("label", name)),
		provider=str(raw.get("provider", "openai-compatible")),
		base_url=str(raw["base_url"]),
		model=str(raw["model"]),
		api_key=raw.get("api_key"),
		api_key_vault=raw.get("api_key_vault"),
		tool_calling=bool(raw.get("tool_calling", False)),
		notes=str(raw.get("notes", "")),
	)


def load_registry(path: Path | None = None) -> ModelRegistry:
	cfg_path = path or registry_path()
	with cfg_path.open(encoding="utf-8") as f:
		data = yaml.safe_load(f)

	profiles: dict[str, Profile] = {}
	for name, raw in (data.get("profiles") or {}).items():
		profiles[name] = _parse_profile(name, raw)

	tc = data.get("tri_chat") or {}
	tri_chat = TriChatConfig(
		turn_order=list(tc.get("turn_order") or ["user", "local", "external"]),
		local_profile=str(tc.get("local_profile", "chat_profile")),
		external_profile=str(tc.get("external_profile", "external_profile")),
	)
	return ModelRegistry(profiles=profiles, tri_chat=tri_chat)


def get_profile(registry: ModelRegistry, name: str) -> Profile:
	if name not in registry.profiles:
		known = ", ".join(sorted(registry.profiles))
		raise KeyError(f"Unknown profile '{name}'. Known: {known}")
	return registry.profiles[name]
