from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from ada.vault import Vault, VaultSession
from ada.vault_unlock import LOCAL_API_KEY_VAULT_KEY, bootstrap_vault_session, ensure_local_api_key


def test_bootstrap_vault_session_from_fd(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	v = Vault(path)
	v.init("pw1")
	r, w = os.pipe()
	os.write(w, b"pw1")
	os.close(w)
	with patch.dict(os.environ, {"ADA_VAULT_UNLOCK_FD": str(r)}, clear=False):
		os.environ.pop("ADA_VAULT_PASSWORD", None)
		session = bootstrap_vault_session(vault=v)
	assert session is not None
	assert session.is_unlocked


def test_bootstrap_returns_none_when_no_vault(tmp_path):
	path = tmp_path / "missing.vault.enc"
	v = Vault(path)
	assert bootstrap_vault_session(vault=v) is None


def test_ensure_local_api_key_generates_once(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	v = Vault(path)
	v.init("pw1")
	session = VaultSession.unlock_from_password(v, "pw1")
	key1 = ensure_local_api_key(session)
	key2 = ensure_local_api_key(VaultSession.unlock_from_password(v, "pw1"))
	assert key1 == key2
	assert key1
	reloaded = VaultSession.unlock_from_password(v, "pw1")
	assert reloaded.get(LOCAL_API_KEY_VAULT_KEY) == key1


def test_legacy_env_scrubbed_on_bootstrap(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	v = Vault(path)
	v.init("pw1")
	r, w = os.pipe()
	os.write(w, b"pw1")
	os.close(w)
	with patch.dict(os.environ, {"ADA_VAULT_UNLOCK_FD": str(r), "ADA_VAULT_PASSWORD": "x"}, clear=False):
		bootstrap_vault_session(vault=v)
	assert "ADA_VAULT_PASSWORD" not in os.environ
