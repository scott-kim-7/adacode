from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from ada.ports import agent_port, mlx_port
from ada.registry import Profile


def api_root(base_url: str) -> str:
	root = base_url.rstrip("/")
	if root.endswith("/v1"):
		return root[: -len("/v1")].rstrip("/")
	return root


def mlx_upstream_base(base_url: str) -> str:
	override = os.environ.get("MLX_UPSTREAM", "").strip().rstrip("/")
	if override:
		return override
	root = api_root(base_url)
	parsed = urlparse(root)
	agent_port_val = agent_port()
	mlx_port_val = mlx_port()
	if parsed.port is not None and parsed.port == agent_port_val:
		host = parsed.hostname or "127.0.0.1"
		scheme = parsed.scheme or "http"
		return f"{scheme}://{host}:{mlx_port_val}"
	return root


def health_url(base_url: str) -> str:
	return f"{mlx_upstream_base(base_url)}/health"


def loaded_model_from_health(
	base_url: str,
	*,
	api_key: str = "local",
	timeout: float = 10.0,
) -> str | None:
	url = health_url(base_url)
	headers = {"Authorization": f"Bearer {api_key}"}
	try:
		with httpx.Client(timeout=timeout) as client:
			resp = client.get(url, headers=headers)
			resp.raise_for_status()
			data = resp.json()
	except httpx.HTTPError:
		return None
	if not isinstance(data, dict):
		return None
	loaded = data.get("loaded_model")
	if loaded:
		return str(loaded)
	return None


def list_model_ids(
	base_url: str,
	*,
	api_key: str = "local",
	timeout: float = 10.0,
) -> list[str]:
	root = base_url.rstrip("/")
	if root.endswith("/v1"):
		url = f"{root}/models"
	else:
		url = f"{root}/v1/models"
	headers = {"Authorization": f"Bearer {api_key}"}
	with httpx.Client(timeout=timeout) as client:
		resp = client.get(url, headers=headers)
		resp.raise_for_status()
		data = resp.json()
	items = data.get("data") if isinstance(data, dict) else None
	if not isinstance(items, list):
		raise RuntimeError(f"Unexpected /v1/models response from {url}")
	ids: list[str] = []
	for item in items:
		if isinstance(item, dict) and item.get("id"):
			ids.append(str(item["id"]))
	if not ids:
		raise RuntimeError(f"No models returned from {url}")
	return ids


class NoLoadedModelError(RuntimeError):
	"""Raised when the LLM server has not loaded a model yet (GET /health loaded_model is null)."""


def effective_model_id(
	base_url: str,
	requested: str | None = None,
	*,
	api_key: str = "local",
	timeout: float = 10.0,
) -> str:
	"""Use mlx_vlm's loaded model (--model / preload). Fall back to request body only if none loaded."""
	loaded = loaded_model_from_health(base_url, api_key=api_key, timeout=timeout)
	if loaded:
		return loaded
	req = (requested or "").strip()
	if req:
		return req
	health = health_url(base_url)
	raise NoLoadedModelError(
		f"No model loaded on LLM server ({health} → loaded_model is null). "
		"Start mlx_vlm with --model …, or pick a model in the chat UI."
	)


def resolve_model_id(
	base_url: str,
	*,
	api_key: str = "local",
	timeout: float = 10.0,
) -> str:
	"""Return the model id currently loaded on the OpenAPI server (mlx_vlm /health)."""
	return effective_model_id(base_url, None, api_key=api_key, timeout=timeout)


def resolve_model_for_profile(profile: Profile, *, timeout: float = 10.0) -> str:
	api_key = profile.api_key or "local"
	return resolve_model_id(profile.base_url, api_key=api_key, timeout=timeout)
