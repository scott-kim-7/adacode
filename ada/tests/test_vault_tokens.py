"""Gmail vault token parsing and readiness."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ada.email.vault_tokens import GMAIL_CLIENT_VAULT_KEY, GmailVaultTokens
from ada.vault import Vault, VaultError, VaultSession


def test_oauth_readiness_survives_invalid_client_json(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	# Simulates vault-ensure / corrupt value — non-JSON token
	session.set(GMAIL_CLIENT_VAULT_KEY, "not-valid-json-token")
	session.save()

	tokens = GmailVaultTokens(session)
	readiness = tokens.oauth_readiness()

	assert readiness.vault_file is True
	assert readiness.vault_unlocked is True
	assert readiness.gmail_client is False
	assert readiness.gmail_client_status == "invalid"
	assert readiness.ready is False
	assert any("vault-set" in step for step in readiness.steps)


def test_get_client_credentials_rejects_invalid_json(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	session.set(GMAIL_CLIENT_VAULT_KEY, "auto-generated-urlsafe-secret")
	session.save()

	tokens = GmailVaultTokens(session)
	with pytest.raises(VaultError, match="not valid JSON"):
		tokens.get_client_credentials()


def test_get_client_credentials_accepts_valid_json(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	session.set(
		GMAIL_CLIENT_VAULT_KEY,
		'{"client_id":"id.apps.googleusercontent.com","client_secret":"sec"}',
	)
	session.save()

	tokens = GmailVaultTokens(session)
	creds = tokens.get_client_credentials()
	assert creds.client_id.endswith(".apps.googleusercontent.com")
	assert creds.client_secret == "sec"
	readiness = tokens.oauth_readiness()
	assert readiness.ready is True


def test_save_client_credentials_via_api(tmp_path, monkeypatch):
	from fastapi.testclient import TestClient

	from ada.agent.server import create_app
	from ada.email.auth import configure_local_api_key
	from ada.email.platform import EmailPlatform

	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	session.set(GMAIL_CLIENT_VAULT_KEY, "bad-value")
	session.save()

	configure_local_api_key("test-key")
	monkeypatch.setattr("ada.email.vault_tokens.Vault", lambda: Vault(path))
	db_path = tmp_path / "email.sqlite3"
	with monkeypatch.context() as m:
		m.setenv("ADA_EMAIL_DB_PATH", str(db_path))
		m.setenv("ADA_HEARTBEAT_ENABLED", "0")
		platform = EmailPlatform.from_session(session)
		client = TestClient(create_app(email_platform=platform))
		resp = client.put(
			"/ops/email/oauth-client",
			json={
				"client_id": "id.apps.googleusercontent.com",
				"client_secret": "sec",
			},
			headers={"X-Ada-Local-Key": "test-key"},
		)

	assert resp.status_code == 200
	body = resp.json()
	assert body["saved"] is True
	assert body["ready"] is True
	reloaded = VaultSession.unlock_from_password(vault, "pw1")
	assert "apps.googleusercontent.com" in (reloaded.get(GMAIL_CLIENT_VAULT_KEY) or "")


def test_health_survives_invalid_gmail_client_json(tmp_path, monkeypatch):
	from fastapi.testclient import TestClient

	from ada.agent.server import create_app
	from ada.email.platform import EmailPlatform

	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	session.set(GMAIL_CLIENT_VAULT_KEY, "auto-generated-urlsafe-secret")
	session.save()

	monkeypatch.setattr("ada.email.vault_tokens.Vault", lambda: Vault(path))
	with patch.dict("os.environ", {"ADA_HEARTBEAT_ENABLED": "0"}, clear=False):
		platform = EmailPlatform.from_session(session)
		client = TestClient(create_app(email_platform=platform))
		resp = client.get("/health")

	assert resp.status_code == 200
	body = resp.json()
	assert body["status"] == "ok"
	assert body["email_vault"] == "client_credentials_required"
