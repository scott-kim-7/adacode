from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ada.vault import Vault, VaultError, VaultSession

GMAIL_CLIENT_VAULT_KEY = "gmail.oauth.client"
GOOGLE_OAUTH_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"


@dataclass(frozen=True)
class OAuthReadiness:
	ready: bool
	vault_file: bool
	vault_unlocked: bool
	gmail_client: bool
	gmail_client_status: str
	steps: tuple[str, ...]

	def blocking_message(self) -> str:
		if self.ready:
			return ""
		return " ".join(self.steps)


@dataclass(frozen=True)
class GmailClientCredentials:
	client_id: str
	client_secret: str


@dataclass(frozen=True)
class GmailAccountTokens:
	access_token: str
	refresh_token: str
	token_uri: str
	client_id: str
	client_secret: str
	scopes: list[str]
	expiry: str | None = None


class GmailVaultTokens:
	def __init__(self, session: VaultSession | None) -> None:
		self._session = session
		self._vault = Vault()

	def is_configured(self) -> bool:
		return self.oauth_readiness().ready

	@staticmethod
	def _parse_json_object(raw: str, vault_key: str) -> dict[str, Any]:
		stripped = raw.strip()
		if not stripped:
			raise VaultError(f"Vault key {vault_key!r} is empty")
		try:
			data = json.loads(stripped)
		except json.JSONDecodeError as exc:
			raise VaultError(
				f"Vault key {vault_key!r} is not valid JSON ({exc}). "
				f"Run: cd ada && make vault-set KEY={vault_key} "
				'(JSON: {"client_id":"...","client_secret":"..."})'
			) from exc
		if not isinstance(data, dict):
			raise VaultError(f"Vault key {vault_key!r} must be a JSON object")
		return data

	def oauth_readiness(self) -> OAuthReadiness:
		vault_file = self._vault.exists()
		vault_unlocked = self._session is not None and self._session.is_unlocked
		gmail_client = False
		gmail_client_status = "missing"
		if vault_unlocked:
			try:
				self.get_client_credentials()
				gmail_client = True
				gmail_client_status = "ok"
			except VaultError as exc:
				gmail_client = False
				msg = str(exc).lower()
				if "not found" in msg or "is empty" in msg:
					gmail_client_status = "missing"
				else:
					gmail_client_status = "invalid"

		steps: list[str] = []
		if not vault_file:
			steps.append("Vault not initialized. Run: cd ada && make vault-init")
		if not vault_unlocked:
			steps.append(
				"Vault not unlocked. Run: ./scripts/ada.sh restart and enter the vault password"
			)
		if vault_unlocked and not gmail_client:
			steps.append(
				"Enter Google OAuth client ID and secret below (stored encrypted in vault), "
				"or run: cd ada && make vault-set KEY=gmail.oauth.client"
			)
		if vault_unlocked and gmail_client:
			from ada.ports import gmail_oauth_redirect_uri

			uri = gmail_oauth_redirect_uri()
			steps.append(
				"Google Cloud Console → Credentials → your OAuth client → Authorized redirect URIs → "
				f"add exactly: {uri} (required after Agent port change to :9082)"
			)

		return OAuthReadiness(
			ready=vault_unlocked and gmail_client,
			vault_file=vault_file,
			vault_unlocked=vault_unlocked,
			gmail_client=gmail_client,
			gmail_client_status=gmail_client_status,
			steps=tuple(steps),
		)

	def get_client_credentials(self) -> GmailClientCredentials:
		raw = self._read_key(GMAIL_CLIENT_VAULT_KEY)
		data = self._parse_json_object(raw, GMAIL_CLIENT_VAULT_KEY)
		try:
			client_id = str(data["client_id"])
			client_secret = str(data["client_secret"])
		except KeyError as exc:
			raise VaultError(
				f"Vault key {GMAIL_CLIENT_VAULT_KEY!r} must include client_id and client_secret. "
				f"Run: cd ada && make vault-set KEY={GMAIL_CLIENT_VAULT_KEY}"
			) from exc
		if not client_id.strip() or not client_secret.strip():
			raise VaultError(
				f"Vault key {GMAIL_CLIENT_VAULT_KEY!r} has empty client_id or client_secret. "
				f"Run: cd ada && make vault-set KEY={GMAIL_CLIENT_VAULT_KEY}"
			)
		return GmailClientCredentials(client_id=client_id, client_secret=client_secret)

	def save_client_credentials(self, client_id: str, client_secret: str) -> None:
		cid = client_id.strip()
		secret = client_secret.strip()
		if not cid or not secret:
			raise VaultError("client_id and client_secret are required")
		payload = json.dumps({"client_id": cid, "client_secret": secret}, ensure_ascii=True)
		self._write_key(GMAIL_CLIENT_VAULT_KEY, payload)
		# Validate round-trip shape before returning.
		self.get_client_credentials()

	def get_account_tokens(self, account_id: str) -> GmailAccountTokens:
		vault_key = f"gmail.oauth.{account_id}"
		raw = self._read_key(vault_key)
		data = self._parse_json_object(raw, vault_key)
		return GmailAccountTokens(
			access_token=str(data.get("access_token") or ""),
			refresh_token=str(data.get("refresh_token") or ""),
			token_uri=str(data.get("token_uri") or "https://oauth2.googleapis.com/token"),
			client_id=str(data.get("client_id") or ""),
			client_secret=str(data.get("client_secret") or ""),
			scopes=[str(s) for s in data.get("scopes") or []],
			expiry=data.get("expiry"),
		)

	def save_account_tokens(self, account_id: str, payload: dict[str, Any]) -> None:
		self._write_key(f"gmail.oauth.{account_id}", json.dumps(payload, ensure_ascii=True))

	def delete_account_tokens(self, account_id: str) -> None:
		if not self._session or not self._session.is_unlocked:
			return
		self._session.delete(f"gmail.oauth.{account_id}")
		self._session.save()

	def _read_key(self, key: str) -> str:
		if not self._session or not self._session.is_unlocked:
			raise VaultError("Vault is not unlocked")
		value = self._session.get(key)
		if not value:
			raise VaultError(f"Vault key not found: {key}")
		return value

	def _write_key(self, key: str, value: str) -> None:
		if not self._session or not self._session.is_unlocked:
			raise VaultError("Vault is not unlocked")
		self._session.set(key, value)
		self._session.save()
