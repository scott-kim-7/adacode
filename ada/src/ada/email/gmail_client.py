from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ada.email.vault_tokens import GmailAccountTokens, GmailClientCredentials, GmailVaultTokens

GMAIL_SCOPES = [
	"https://www.googleapis.com/auth/gmail.readonly",
	"https://www.googleapis.com/auth/gmail.send",
]
REDIRECT_URI = "http://127.0.0.1:8082/oauth/gmail/callback"


class GmailApiClient(Protocol):
	def list_history(self, start_history_id: str) -> dict[str, Any]: ...

	def get_message(self, message_id: str, *, fmt: str = "full") -> dict[str, Any]: ...

	def get_raw_message(self, message_id: str) -> bytes: ...

	def get_attachment(self, message_id: str, attachment_id: str) -> bytes: ...

	def get_profile(self) -> dict[str, Any]: ...

	def list_latest_message_id(self) -> str | None: ...

	def list_recent_message_ids(self, *, max_results: int = 50) -> list[str]: ...

	def send_raw(self, raw_bytes: bytes) -> str: ...

	def refresh(self) -> GmailAccountTokens: ...


@dataclass
class GoogleGmailClient:
	account_id: str
	credentials: Credentials
	_service: Any = None

	def __post_init__(self) -> None:
		if self._service is None:
			self._service = build("gmail", "v1", credentials=self.credentials, cache_discovery=False)

	@property
	def service(self) -> Any:
		return self._service

	def list_history(self, start_history_id: str) -> dict[str, Any]:
		return (
			self.service.users()
			.history()
			.list(userId="me", startHistoryId=start_history_id, historyTypes=["messageAdded"])
			.execute()
		)

	def get_message(self, message_id: str, *, fmt: str = "full") -> dict[str, Any]:
		return self.service.users().messages().get(userId="me", id=message_id, format=fmt).execute()

	def get_raw_message(self, message_id: str) -> bytes:
		payload = self.get_message(message_id, fmt="raw")
		import base64

		raw = str(payload.get("raw") or "")
		padded = raw + "=" * (-len(raw) % 4)
		return base64.urlsafe_b64decode(padded.encode("ascii"))

	def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
		payload = (
			self.service.users()
			.messages()
			.attachments()
			.get(userId="me", messageId=message_id, id=attachment_id)
			.execute()
		)
		import base64

		data = str(payload.get("data") or "")
		padded = data + "=" * (-len(data) % 4)
		return base64.urlsafe_b64decode(padded.encode("ascii"))

	def get_profile(self) -> dict[str, Any]:
		return self.service.users().getProfile(userId="me").execute()

	def list_latest_message_id(self) -> str | None:
		result = self.service.users().messages().list(userId="me", maxResults=1).execute()
		messages = result.get("messages") or []
		if not messages:
			return None
		return str(messages[0]["id"])

	def list_recent_message_ids(self, *, max_results: int = 50) -> list[str]:
		limit = max(1, min(100, int(max_results)))
		result = self.service.users().messages().list(userId="me", maxResults=limit).execute()
		messages = result.get("messages") or []
		return [str(item["id"]) for item in messages if item.get("id")]

	def send_raw(self, raw_bytes: bytes) -> str:
		import base64

		encoded = base64.urlsafe_b64encode(raw_bytes).decode("ascii")
		sent = self.service.users().messages().send(userId="me", body={"raw": encoded}).execute()
		return str(sent.get("id") or "")

	def refresh(self) -> GmailAccountTokens:
		self.credentials.refresh(Request())
		return tokens_from_credentials(self.account_id, self.credentials)


def tokens_from_credentials(account_id: str, creds: Credentials) -> GmailAccountTokens:
	expiry = creds.expiry.isoformat() if creds.expiry else None
	return GmailAccountTokens(
		access_token=str(creds.token or ""),
		refresh_token=str(creds.refresh_token or ""),
		token_uri=str(creds.token_uri or "https://oauth2.googleapis.com/token"),
		client_id=str(creds.client_id or ""),
		client_secret=str(creds.client_secret or ""),
		scopes=list(creds.scopes or []),
		expiry=expiry,
	)


def credentials_from_tokens(tokens: GmailAccountTokens) -> Credentials:
	return Credentials(
		token=tokens.access_token,
		refresh_token=tokens.refresh_token,
		token_uri=tokens.token_uri,
		client_id=tokens.client_id,
		client_secret=tokens.client_secret,
		scopes=tokens.scopes or GMAIL_SCOPES,
	)


def tokens_to_dict(tokens: GmailAccountTokens) -> dict[str, Any]:
	return {
		"access_token": tokens.access_token,
		"refresh_token": tokens.refresh_token,
		"token_uri": tokens.token_uri,
		"client_id": tokens.client_id,
		"client_secret": tokens.client_secret,
		"scopes": tokens.scopes,
		"expiry": tokens.expiry,
	}


def build_gmail_client(
	account_id: str,
	vault: GmailVaultTokens,
) -> GoogleGmailClient:
	tokens = vault.get_account_tokens(account_id)
	creds = credentials_from_tokens(tokens)
	return GoogleGmailClient(account_id=account_id, credentials=creds)


def seed_history_id(client: GmailApiClient) -> str:
	latest = client.list_latest_message_id()
	if latest:
		message = client.get_message(latest, fmt="minimal")
		history_id = str(message.get("historyId") or "")
		if history_id:
			return history_id
	profile = client.get_profile()
	return str(profile.get("historyId") or "")


def is_history_id_expired(exc: Exception) -> bool:
	if isinstance(exc, HttpError):
		try:
			return int(exc.resp.status) == 404
		except Exception:
			return False
	return False


def oauth_client_config(vault: GmailVaultTokens) -> dict[str, Any]:
	creds = vault.get_client_credentials()
	return {
		"web": {
			"client_id": creds.client_id,
			"client_secret": creds.client_secret,
			"auth_uri": "https://accounts.google.com/o/oauth2/auth",
			"token_uri": "https://oauth2.googleapis.com/token",
			"redirect_uris": [REDIRECT_URI],
		}
	}


def utc_now_iso() -> str:
	return datetime.now(UTC).isoformat()
