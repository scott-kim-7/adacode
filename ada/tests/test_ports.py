from __future__ import annotations

import os

import pytest

from ada.ports import (
	DEFAULT_AGENT_PORT,
	DEFAULT_MLX_PORT,
	PortConfigError,
	agent_port,
	assert_agent_port_allowed,
	gmail_oauth_redirect_uri,
	is_mlx_reserved_port,
	mlx_port,
)


def test_default_agent_port_outside_mlx_range():
	assert DEFAULT_AGENT_PORT == 9082
	assert DEFAULT_MLX_PORT == 8089
	assert not is_mlx_reserved_port(DEFAULT_AGENT_PORT)
	assert is_mlx_reserved_port(DEFAULT_MLX_PORT)


def test_default_mlx_port(monkeypatch):
	monkeypatch.delenv("ADA_MLX_PORT", raising=False)
	assert mlx_port() == 8089


def test_reserved_range_rejects_mlx_ports():
	for port in (8080, 8082, 8090):
		with pytest.raises(PortConfigError):
			assert_agent_port_allowed(port)


def test_agent_port_env_override(monkeypatch):
	monkeypatch.setenv("ADA_AGENT_PORT", "9180")
	monkeypatch.delenv("ADA_AGENT_HOST", raising=False)
	assert agent_port() == 9180
	assert gmail_oauth_redirect_uri() == "http://127.0.0.1:9180/oauth/gmail/callback"


def test_agent_port_rejects_mlx_reserved_env(monkeypatch):
	monkeypatch.setenv("ADA_AGENT_PORT", "8085")
	with pytest.raises(PortConfigError):
		agent_port()


def test_gmail_redirect_uri_uses_host(monkeypatch):
	monkeypatch.setenv("ADA_AGENT_PORT", "9200")
	monkeypatch.setenv("ADA_AGENT_HOST", "127.0.0.1")
	assert gmail_oauth_redirect_uri() == "http://127.0.0.1:9200/oauth/gmail/callback"
	monkeypatch.delenv("ADA_AGENT_PORT", raising=False)
	monkeypatch.delenv("ADA_AGENT_HOST", raising=False)
