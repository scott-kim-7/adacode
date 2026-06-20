from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ada.agent.config import AgentConfig, ModelsConfig, load_agent_config
from ada.paths import ada_root


def agent_config_path() -> Path:
	return ada_root() / "config" / "agent.yaml"


def _models_to_yaml(models: ModelsConfig) -> dict[str, Any]:
	payload: dict[str, Any] = {
		"chat": {
			"base_url": models.chat.base_url,
			"model_id": models.chat.model_id,
			"api_key": models.chat.api_key,
		},
		"task": {
			"base_url": models.task.base_url,
			"model_id": models.task.model_id,
			"api_key": models.task.api_key,
		},
		"tool": models.tool_alias,
	}
	if models.task.max_tokens is not None:
		payload["task"]["max_tokens"] = models.task.max_tokens
	return payload


def save_models_config(models: ModelsConfig, path: Path | None = None) -> AgentConfig:
	config_path = path or agent_config_path()
	raw: dict[str, Any] = {}
	if config_path.is_file():
		loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
		if isinstance(loaded, dict):
			raw = loaded
	raw["models"] = _models_to_yaml(models)
	tmp_path = config_path.with_suffix(".yaml.tmp")
	tmp_path.write_text(
		yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
		encoding="utf-8",
	)
	tmp_path.replace(config_path)
	return load_agent_config(config_path)


def update_agent_models(models: ModelsConfig) -> AgentConfig:
	return save_models_config(models)
