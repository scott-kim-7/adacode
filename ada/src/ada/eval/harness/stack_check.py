from __future__ import annotations

import os
from typing import Any

import httpx

from ada.eval.harness.config import eval_base_url, load_eval_config
from ada.registry import get_profile, load_registry


def agent_health_url() -> str:
	base = eval_base_url().rstrip("/")
	if base.endswith("/v1"):
		return base[: -len("/v1")] + "/health"
	return base + "/health"


def is_agent_reachable(timeout: float = 2.0) -> bool:
	try:
		with httpx.Client(timeout=timeout) as client:
			resp = client.get(agent_health_url())
			return resp.status_code == 200
	except httpx.HTTPError:
		return False


def is_mlx_reachable(timeout: float = 2.0) -> bool:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	profile = get_profile(load_registry(), profile_name)
	url = f"{profile.base_url.rstrip('/')}/models"
	try:
		with httpx.Client(timeout=timeout) as client:
			resp = client.get(url, headers={"Authorization": "Bearer local"})
			return resp.status_code == 200
	except httpx.HTTPError:
		return False


def stack_status() -> dict[str, Any]:
	return {
		"agent_reachable": is_agent_reachable(),
		"mlx_reachable": is_mlx_reachable(),
		"endpoint": eval_base_url(),
	}
