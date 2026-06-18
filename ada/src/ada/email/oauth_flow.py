from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

from google_auth_oauthlib.flow import Flow

from ada.email.gmail_client import GMAIL_SCOPES, REDIRECT_URI, oauth_client_config, tokens_from_credentials
from ada.email.vault_tokens import GmailVaultTokens


@dataclass(frozen=True)
class PendingOAuth:
	account_id: str
	code_verifier: str


@dataclass
class OAuthStateStore:
	"""In-memory OAuth state + PKCE verifier (single Agent process)."""

	_states: dict[str, PendingOAuth] = field(default_factory=dict)

	def reserve_account_id(self, account_id: str | None = None) -> str:
		return account_id or f"acct-{uuid.uuid4().hex[:12]}"

	def bind(self, state: str, account_id: str, code_verifier: str) -> None:
		if not state.strip():
			raise ValueError("OAuth state is required")
		if not code_verifier.strip():
			raise ValueError("PKCE code_verifier is required")
		self._states[state] = PendingOAuth(account_id=account_id, code_verifier=code_verifier)

	def pop(self, state: str) -> PendingOAuth | None:
		return self._states.pop(state, None)


class GmailOAuthService:
	def __init__(self, vault: GmailVaultTokens, *, state_store: OAuthStateStore | None = None) -> None:
		self._vault = vault
		self._states = state_store or OAuthStateStore()

	def start(self, account_id: str | None = None) -> dict[str, str]:
		readiness = self._vault.oauth_readiness()
		if not readiness.ready:
			message = readiness.blocking_message() or "Vault is not configured for Gmail OAuth"
			raise RuntimeError(message)
		resolved_account_id = self._states.reserve_account_id(account_id)
		state = secrets.token_urlsafe(24)
		flow = Flow.from_client_config(
			oauth_client_config(self._vault),
			scopes=GMAIL_SCOPES,
			redirect_uri=REDIRECT_URI,
			state=state,
		)
		auth_url, _ = flow.authorization_url(
			access_type="offline",
			include_granted_scopes="true",
			prompt="consent",
		)
		code_verifier = flow.code_verifier
		if not code_verifier:
			raise RuntimeError("PKCE code_verifier was not generated for Gmail OAuth")
		self._states.bind(state, resolved_account_id, code_verifier)
		return {
			"authorization_url": auth_url,
			"state": state,
			"account_id": resolved_account_id,
		}

	def complete(self, *, code: str, state: str) -> dict[str, Any]:
		pending = self._states.pop(state)
		if not pending:
			raise ValueError("invalid or expired OAuth state")
		flow = Flow.from_client_config(
			oauth_client_config(self._vault),
			scopes=GMAIL_SCOPES,
			redirect_uri=REDIRECT_URI,
			state=state,
			code_verifier=pending.code_verifier,
			autogenerate_code_verifier=False,
		)
		flow.fetch_token(code=code)
		creds = flow.credentials
		tokens = tokens_from_credentials(pending.account_id, creds)
		self._vault.save_account_tokens(pending.account_id, {
			"access_token": tokens.access_token,
			"refresh_token": tokens.refresh_token,
			"token_uri": tokens.token_uri,
			"client_id": tokens.client_id,
			"client_secret": tokens.client_secret,
			"scopes": tokens.scopes,
			"expiry": tokens.expiry,
		})
		return {"account_id": pending.account_id, "status": "connected"}
