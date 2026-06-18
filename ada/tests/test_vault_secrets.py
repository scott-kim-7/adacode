"""Tests for vault-only secret storage policy."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from ada.llm import resolve_api_key
from ada.registry import Profile
from ada.vault_secrets import (
	assert_profile_secret_policy,
	ensure_vault_secret,
	generate_vault_secret,
	scrub_forbidden_secret_env,
	store_secret_in_vault,
)
from ada.vault import Vault, VaultSession


def test_scrub_forbidden_secret_env():
	with patch.dict(
		os.environ,
		{"ADA_EXTERNAL_API_KEY": "sk-leak", "ADA_VAULT_PASSWORD": "pw", "ADA_SAFE": "1"},
		clear=False,
	):
		removed = scrub_forbidden_secret_env()
		assert "ADA_EXTERNAL_API_KEY" in removed
		assert "ADA_VAULT_PASSWORD" in removed
		assert "ADA_EXTERNAL_API_KEY" not in os.environ
		assert os.environ.get("ADA_SAFE") == "1"


def test_resolve_api_key_rejects_env_bypass():
	profile = Profile(
		name="external",
		label="x",
		provider="openai-compatible",
		base_url="https://api.example/v1",
		api_key_vault="external.openai.api_key",
	)
	with patch.dict(os.environ, {"ADA_EXTERNAL_API_KEY": "sk-from-env"}, clear=False):
		scrub_forbidden_secret_env()
		with pytest.raises(Exception):
			resolve_api_key(profile, vault_session=None)


def test_assert_profile_rejects_plaintext_api_key():
	with pytest.raises(Exception):
		assert_profile_secret_policy("bad", "sk-secret", None)


def test_store_secret_in_vault_roundtrip(tmp_path, monkeypatch):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	monkeypatch.setattr("ada.vault_secrets.Vault", lambda: Vault(path))
	monkeypatch.setattr("ada.vault_secrets.prompt_password", lambda _a: "pw1")
	value = bytearray(b"my-secret-token")
	store_secret_in_vault("test.secret", value, unlock_action="VAULT_SET")
	assert value == bytearray(len(value))  # zeroed
	reloaded = VaultSession.unlock_from_password(vault, "pw1")
	assert reloaded.get("test.secret") == "my-secret-token"


def test_ensure_vault_secret_idempotent(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	value1, created1 = ensure_vault_secret(session, "auto.key")
	assert created1 is True
	assert len(value1) >= 32
	session2 = VaultSession.unlock_from_password(vault, "pw1")
	value2, created2 = ensure_vault_secret(session2, "auto.key")
	assert created2 is False
	assert value2 == value1


def test_ensure_vault_secret_force_regenerates(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	first, _ = ensure_vault_secret(session, "rotating.key")
	session2 = VaultSession.unlock_from_password(vault, "pw1")
	second, created = ensure_vault_secret(session2, "rotating.key", force=True)
	assert created is True
	assert second != first


def test_generate_vault_secret_minimum_length():
	with pytest.raises(Exception):
		generate_vault_secret(nbytes=8)


def test_ensure_vault_secret_rejects_manual_input_keys(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	with pytest.raises(Exception, match="cannot be auto-generated"):
		ensure_vault_secret(session, "gmail.oauth.client")
