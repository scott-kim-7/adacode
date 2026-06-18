from __future__ import annotations

import os

DEFAULT_AGENT_PORT = 9082
DEFAULT_MLX_PORT = 8089
DEFAULT_MLX_PROXY_PORT = 9081
MLX_RESERVED_PORT_MIN = 8080
MLX_RESERVED_PORT_MAX = 8090


class PortConfigError(ValueError):
	pass


def _env_int(name: str, default: int) -> int:
	raw = os.environ.get(name, "").strip()
	if not raw:
		return default
	try:
		return int(raw)
	except ValueError as exc:
		raise PortConfigError(f"Invalid {name}={raw!r} (expected integer)") from exc


def agent_host() -> str:
	return os.environ.get("ADA_AGENT_HOST", "127.0.0.1").strip() or "127.0.0.1"


def agent_port() -> int:
	port = _env_int("ADA_AGENT_PORT", DEFAULT_AGENT_PORT)
	assert_agent_port_allowed(port)
	return port


def mlx_port() -> int:
	return _env_int("ADA_MLX_PORT", DEFAULT_MLX_PORT)


def mlx_host() -> str:
	return os.environ.get("ADA_MLX_HOST", "127.0.0.1").strip() or "127.0.0.1"


def mlx_upstream_url() -> str:
	override = os.environ.get("MLX_UPSTREAM", "").strip().rstrip("/")
	if override:
		return override
	return f"http://{mlx_host()}:{mlx_port()}"


def mlx_proxy_port() -> int:
	return _env_int("ADA_MLX_PROXY_PORT", DEFAULT_MLX_PROXY_PORT)


def is_mlx_reserved_port(port: int) -> bool:
	return MLX_RESERVED_PORT_MIN <= port <= MLX_RESERVED_PORT_MAX


def assert_agent_port_allowed(port: int) -> None:
	if is_mlx_reserved_port(port):
		raise PortConfigError(
			f"ADA_AGENT_PORT={port} is in the MLX reserved range "
			f"({MLX_RESERVED_PORT_MIN}-{MLX_RESERVED_PORT_MAX}). "
			f"Use {DEFAULT_AGENT_PORT} or another port outside that range."
		)


def gmail_oauth_redirect_uri() -> str:
	return f"http://{agent_host()}:{agent_port()}/oauth/gmail/callback"


def agent_base_url(*, host: str | None = None, port: int | None = None) -> str:
	h = host or agent_host()
	p = port if port is not None else agent_port()
	return f"http://{h}:{p}"
