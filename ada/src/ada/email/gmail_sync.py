from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ada.email.attachment_store import AttachmentStore
from ada.email.gmail_client import GmailApiClient, is_history_id_expired, seed_history_id
from ada.email.gmail_parse import parse_gmail_message
from ada.email.service import EmailConversationService, GmailAttachment, IngestedMessage
from ada.email.store import EmailStore


def _utc_now() -> str:
	return datetime.now(UTC).isoformat()


class GmailSyncService:
	def __init__(
		self,
		store: EmailStore,
		email_service: EmailConversationService,
		attachment_store: AttachmentStore,
		*,
		client_factory: Callable[[str], GmailApiClient],
		defer_reply_review: Callable[[str], None] | None = None,
	) -> None:
		self._store = store
		self._email_service = email_service
		self._attachment_store = attachment_store
		self._client_factory = client_factory
		self._defer_reply_review = defer_reply_review

	def sync_account(self, account_id: str) -> dict[str, Any]:
		settings = self._store.get_email_settings()
		if not bool(settings.get("email_service_enabled", True)):
			return {"account_id": account_id, "skipped": True, "reason": "email_service_disabled"}
		account = self._store.get_account(account_id)
		if not account or str(account.get("status")) != "active":
			return {"account_id": account_id, "skipped": True, "reason": "inactive"}

		client = self._client_factory(account_id)
		history_id = account.get("gmail_history_id")
		if not history_id:
			history_id = seed_history_id(client)
			self._store.set_account_history_id(account_id, history_id)
			return {"account_id": account_id, "seeded": True, "history_id": history_id}

		try:
			changes = client.list_history(str(history_id))
		except Exception as exc:
			if is_history_id_expired(exc):
				new_id = seed_history_id(client)
				self._store.set_account_history_id(account_id, new_id)
				return {"account_id": account_id, "reseeded": True, "history_id": new_id}
			raise

		processed = 0
		for record in changes.get("history") or []:
			for added in record.get("messagesAdded") or []:
				msg_ref = added.get("message") or {}
				msg_id = str(msg_ref.get("id") or "")
				if not msg_id:
					continue
				if self._store.get_message(msg_id):
					continue
				self._ingest_gmail_message(account_id, str(account.get("email_address") or ""), client, msg_id)
				processed += 1

		new_history = str(changes.get("historyId") or history_id)
		self._store.set_account_history_id(account_id, new_history)
		self.maybe_enqueue_backfill_if_empty(account_id)
		return {"account_id": account_id, "processed": processed, "history_id": new_history}

	def maybe_enqueue_backfill_if_empty(self, account_id: str) -> None:
		if self._store.count_messages({"account_id": account_id}) > 0:
			return
		if self._has_pending_backfill(account_id):
			return
		self.enqueue_backfill(account_id)

	def _has_pending_backfill(self, account_id: str) -> bool:
		for item in self._store.list_pending_deferred_tasks("gmail_backfill"):
			try:
				payload = json.loads(str(item.get("payload_json") or "{}"))
			except json.JSONDecodeError:
				continue
			if str(payload.get("account_id") or "") == account_id:
				return True
		return False

	def enqueue_backfill(self, account_id: str) -> None:
		self._store.enqueue_deferred_task(
			"gmail_backfill",
			json.dumps({"account_id": account_id}, ensure_ascii=True),
			_utc_now(),
		)

	def backfill_recent(self, account_id: str, *, max_results: int | None = None) -> dict[str, Any]:
		settings = self._store.get_email_settings()
		if not bool(settings.get("email_service_enabled", True)):
			return {"account_id": account_id, "skipped": True, "reason": "email_service_disabled"}
		account = self._store.get_account(account_id)
		if not account or str(account.get("status")) != "active":
			return {"account_id": account_id, "skipped": True, "reason": "inactive"}

		limit = max_results
		if limit is None:
			raw_limit = settings.get("gmail_backfill_max_messages", 50)
			limit = int(raw_limit) if isinstance(raw_limit, int) else 50
		limit = max(1, min(100, int(limit)))

		client = self._client_factory(account_id)
		account_email = str(account.get("email_address") or "")
		backfilled = 0
		skipped = 0
		for message_id in client.list_recent_message_ids(max_results=limit):
			if self._store.get_message(message_id):
				skipped += 1
				continue
			self._ingest_gmail_message(account_id, account_email, client, message_id)
			backfilled += 1
		return {"account_id": account_id, "backfilled": backfilled, "skipped": skipped, "limit": limit}

	def _ingest_gmail_message(
		self,
		account_id: str,
		account_email: str,
		client: GmailApiClient,
		message_id: str,
	) -> None:
		raw_bytes = client.get_raw_message(message_id)
		eml_path = self._attachment_store.save_eml(
			account_id=account_id,
			message_id=message_id,
			raw_bytes=raw_bytes,
		)
		full = client.get_message(message_id, fmt="full")
		parsed = parse_gmail_message(full)
		settings = self._store.get_email_settings()
		max_bytes = settings.get("attachment_max_bytes")
		attachments: list[GmailAttachment] = []
		for item in parsed.get("attachments") or []:
			data = client.get_attachment(message_id, str(item["attachment_id"]))
			saved = self._attachment_store.save_attachment(
				account_id=account_id,
				message_id=message_id,
				filename=str(item["filename"]),
				mime_type=str(item["mime_type"]),
				data=data,
				max_bytes=max_bytes if isinstance(max_bytes, int) else None,
			)
			if saved:
				attachments.append(
					GmailAttachment(
						filename=saved.filename,
						mime_type=saved.mime_type,
						size_bytes=saved.size_bytes,
						storage_uri=saved.storage_uri,
					)
				)

		received_at = _utc_now()
		record = IngestedMessage(
			account_id=account_id,
			account_email=account_email,
			message_id=message_id,
			thread_id=str(parsed.get("thread_id") or ""),
			subject=str(parsed.get("subject") or ""),
			body_text=str(parsed.get("body_text") or ""),
			from_address=str(parsed.get("from_address") or ""),
			to_addresses=list(parsed.get("to_addresses") or []),
			headers=dict(parsed.get("headers") or {}),
			participants=list(parsed.get("participants") or []),
			received_at=received_at,
			attachments=tuple(attachments),
		)
		result = self._email_service.ingest_message(record)
		if result.get("inserted"):
			self._store.update_message_eml_path(message_id, eml_path)
			self._store.insert_inbox_item(
				message_id=message_id,
				thread_id=str(parsed.get("thread_id") or ""),
				summary_status="pending",
			)
			if self._defer_reply_review:
				self._defer_reply_review(message_id)

	def enqueue_reply_review(self, message_id: str) -> None:
		self._store.enqueue_deferred_task(
			"gmail_reply_review",
			json.dumps({"message_id": message_id}, ensure_ascii=True),
			_utc_now(),
		)
