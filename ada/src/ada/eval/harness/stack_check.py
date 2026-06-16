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


def _mlx_probe_urls(base: str) -> list[str]:
	root = base.rstrip("/")
	return [f"{root}/health", f"{root}/v1/models"]


def _probe_url(client: httpx.Client, url: str) -> bool:
	headers = {"Authorization": "Bearer local"}
	try:
		resp = client.get(url, headers=headers)
		if resp.status_code == 200:
			return True
		resp = client.get(url)
		return resp.status_code == 200
	except httpx.HTTPError:
		return False


def is_mlx_upstream_reachable(timeout: float = 2.0) -> bool:
	"""Check MLX_UPSTREAM (agent server → MLX), not registry profile alone."""
	upstream = os.environ.get("MLX_UPSTREAM", "http://127.0.0.1:8080").rstrip("/")
	try:
		with httpx.Client(timeout=timeout) as client:
			return any(_probe_url(client, url) for url in _mlx_probe_urls(upstream))
	except httpx.HTTPError:
		return False


def is_mlx_reachable(timeout: float = 2.0) -> bool:
	cfg = load_eval_config()
	profile_name = os.environ.get("ADA_AGENT_PROFILE") or str(cfg.get("model_profile") or "chat_profile")
	profile = get_profile(load_registry(), profile_name)
	base = profile.base_url.rstrip("/")
	if base.endswith("/v1"):
		base = base[: -len("/v1")]
	try:
		with httpx.Client(timeout=timeout) as client:
			return any(_probe_url(client, url) for url in _mlx_probe_urls(base))
	except httpx.HTTPError:
		return False


def stack_status() -> dict[str, Any]:
	return {
		"agent_reachable": is_agent_reachable(),
		"mlx_reachable": is_mlx_reachable(),
		"endpoint": eval_base_url(),
	}


def require_mlx_reachable(*, timeout: float = 2.0) -> None:
	if not is_mlx_reachable(timeout=timeout):
		upstream = os.environ.get("MLX_UPSTREAM", "http://127.0.0.1:8080").rstrip("/")
		raise SystemExit(
			f"LLM server is not reachable at {upstream} (/health or /v1/models) "
			"— start mlx_vlm.server on :8080 before continuing."
		)


def require_agent_stack(*, timeout: float = 2.0) -> None:
	require_mlx_reachable(timeout=timeout)
	if not is_agent_reachable(timeout=timeout):
		raise SystemExit(
			f"Ada Agent API is not reachable at {agent_health_url()} — run ./scripts/ensure-ada-agent-server.sh"
		)
