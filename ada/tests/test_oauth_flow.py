"""Gmail OAuth PKCE state must survive from /start to /callback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ada.email.oauth_flow import GmailOAuthService, OAuthStateStore
from ada.email.vault_tokens import GMAIL_CLIENT_VAULT_KEY, GmailVaultTokens
from ada.vault import Vault, VaultSession


def _ready_vault(tmp_path):
	path = tmp_path / "secrets.vault.enc"
	vault = Vault(path)
	vault.init("pw1")
	session = VaultSession.unlock_from_password(vault, "pw1")
	session.set(
		GMAIL_CLIENT_VAULT_KEY,
		'{"client_id":"id.apps.googleusercontent.com","client_secret":"sec"}',
	)
	session.save()
	return session


def test_oauth_start_stores_pkce_verifier_for_callback(tmp_path):
	session = _ready_vault(tmp_path)
	store = OAuthStateStore()
	service = GmailOAuthService(GmailVaultTokens(session), state_store=store)
	started = service.start()
	assert started["state"]
	pending = store._states[started["state"]]
	assert pending.account_id == started["account_id"]
	assert len(pending.code_verifier) >= 43
	assert "code_challenge=" in started["authorization_url"] or "code_challenge" in started["authorization_url"]


def test_oauth_complete_passes_stored_code_verifier(tmp_path):
	session = _ready_vault(tmp_path)
	store = OAuthStateStore()
	service = GmailOAuthService(GmailVaultTokens(session), state_store=store)
	started = service.start()
	state = started["state"]
	pending = store.pop(state)
	assert pending is not None
	verifier = pending.code_verifier

	captured: dict[str, object] = {}

	def fake_from_client_config(*_args, **kwargs):
		captured.update(kwargs)
		flow = MagicMock()
		flow.fetch_token = MagicMock()
		flow.credentials = MagicMock()
		return flow

	with (
		patch("ada.email.oauth_flow.Flow.from_client_config", side_effect=fake_from_client_config),
		patch("ada.email.oauth_flow.tokens_from_credentials") as mock_tokens,
	):
		mock_tokens.return_value = MagicMock(
			access_token="at",
			refresh_token="rt",
			token_uri="https://oauth2.googleapis.com/token",
			client_id="id",
			client_secret="sec",
			scopes=["scope"],
			expiry=None,
		)
		# Re-bind because start() already popped via our pop() above — simulate full flow:
		store.bind(state, pending.account_id, verifier)
		result = service.complete(code="auth-code", state=state)

	assert captured.get("code_verifier") == verifier
	assert captured.get("autogenerate_code_verifier") is False
	assert result["account_id"] == pending.account_id


def test_oauth_complete_rejects_unknown_state(tmp_path):
	session = _ready_vault(tmp_path)
	service = GmailOAuthService(GmailVaultTokens(session))
	with pytest.raises(ValueError, match="invalid or expired OAuth state"):
		service.complete(code="x", state="missing-state")
