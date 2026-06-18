from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ada.email.policy import DEFAULT_ADA_ALIASES, TriggerDecision, evaluate_reply_policy
from ada.email.gmail_sender import GmailSender
from ada.email.store import EmailMessageRecord, EmailStore


def _utc_now() -> str:
	return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class GmailAttachment:
	filename: str
	mime_type: str
	size_bytes: int
	storage_uri: str


@dataclass(frozen=True)
class IngestedMessage:
	account_id: str
	account_email: str
	message_id: str
	thread_id: str
	subject: str
	body_text: str
	from_address: str
	to_addresses: list[str]
	headers: dict[str, str]
	participants: list[str]
	received_at: str
	attachments: tuple[GmailAttachment, ...]


class EmailConversationService:
	def __init__(
		self,
		store: EmailStore,
		*,
		aliases: tuple[str, ...] = DEFAULT_ADA_ALIASES,
		gmail_sender: GmailSender | None = None,
	) -> None:
		self._store = store
		self._aliases = aliases
		self._gmail_sender = gmail_sender or GmailSender()

	@classmethod
	def from_env(cls) -> EmailConversationService:
		db_env = os.environ.get("ADA_EMAIL_DB_PATH", "").strip()
		db_path = Path(db_env) if db_env else Path(__file__).resolve().parents[3] / "data" / "email_connector.sqlite3"
		return cls(EmailStore(db_path))

	def ingest_message(self, message: IngestedMessage) -> dict[str, Any]:
		self._store.upsert_account(message.account_id, message.account_email)
		self._store.upsert_thread(
			message.thread_id,
			message.subject,
			json.dumps(message.participants, ensure_ascii=True),
			message.received_at,
		)
		inserted = self._store.insert_message(
			EmailMessageRecord(
				message_id=message.message_id,
				thread_id=message.thread_id,
				account_id=message.account_id,
				subject=message.subject,
				body_text=message.body_text,
				from_address=message.from_address,
				to_addresses=",".join(message.to_addresses),
				headers_json=json.dumps(message.headers, ensure_ascii=True),
				received_at=message.received_at,
			)
		)
		if inserted:
			for attachment in message.attachments:
				self._store.insert_attachment(
					message_id=message.message_id,
					filename=attachment.filename,
					mime_type=attachment.mime_type,
					size_bytes=attachment.size_bytes,
					storage_uri=attachment.storage_uri,
				)
		self._store.append_audit_log(
			action_id=None,
			message_id=message.message_id,
			event_type="ingested" if inserted else "duplicate_ignored",
			detail_json=json.dumps(
				{
					"thread_id": message.thread_id,
					"attachment_count": len(message.attachments),
					"received_at": message.received_at,
				},
				ensure_ascii=True,
			),
		)
		return {"message_id": message.message_id, "inserted": inserted}

	def process_message(self, message_id: str, *, allowed_domains: tuple[str, ...] | None = None) -> dict[str, Any]:
		message = self._store.get_message(message_id)
		if not message:
			raise KeyError(f"message not found: {message_id}")

		existing = self._store.get_action_by_message_id(message_id)
		if existing:
			return self._action_result(existing)

		headers = json.loads(str(message.get("headers_json") or "{}"))
		decision: TriggerDecision = evaluate_reply_policy(
			subject=str(message.get("subject") or ""),
			body=str(message.get("body_text") or ""),
			sender=str(message.get("from_address") or ""),
			headers=headers if isinstance(headers, dict) else {},
			aliases=self._aliases,
			allowed_domains=allowed_domains,
		)

		draft_status = "ready" if decision.allowed_to_reply else "not_requested"
		send_status = "pending_review" if decision.allowed_to_reply else "blocked"
		action_id = self._store.create_action(
			message_id=message_id,
			detected_mention=decision.detected_mention,
			detected_reply_intent=decision.detected_reply_intent,
			reason=decision.reason,
			draft_status=draft_status,
			send_status=send_status,
		)
		self._store.append_audit_log(
			action_id=action_id,
			message_id=message_id,
			event_type="policy_evaluated",
			detail_json=json.dumps(
				{
					"detected_mention": decision.detected_mention,
					"detected_reply_intent": decision.detected_reply_intent,
					"allowed_to_reply": decision.allowed_to_reply,
					"reason": decision.reason,
					"evaluated_at": _utc_now(),
				},
				ensure_ascii=True,
			),
		)
		return self._action_result(
			{
				"id": action_id,
				"message_id": message_id,
				"detected_mention": decision.detected_mention,
				"detected_reply_intent": decision.detected_reply_intent,
				"reason": decision.reason,
				"draft_status": draft_status,
				"send_status": send_status,
			}
		)

	def _action_result(self, action: dict[str, Any]) -> dict[str, Any]:
		return {
			"action_id": int(action["id"]),
			"message_id": str(action["message_id"]),
			"detected_mention": bool(action.get("detected_mention")),
			"detected_reply_intent": bool(action.get("detected_reply_intent")),
			"allowed_to_reply": str(action.get("send_status")) == "pending_review",
			"reason": str(action.get("reason") or ""),
			"draft_status": str(action.get("draft_status") or ""),
			"send_status": str(action.get("send_status") or ""),
		}

	def list_pending_reviews(self) -> list[dict[str, Any]]:
		return self._store.list_pending_actions()

	def approve_and_send(self, action_id: int, *, subject: str, body: str) -> dict[str, Any]:
		action = self._store.get_action(action_id)
		if not action:
			raise KeyError(f"action not found: {action_id}")
		if str(action.get("send_status")) != "pending_review":
			raise ValueError("action is not pending_review")
		message_id = str(action.get("message_id") or "")
		message = self._store.get_message(message_id)
		if not message:
			raise KeyError(f"message not found: {message_id}")
		result = self._gmail_sender.send_reply(
			thread_id=str(message.get("thread_id") or ""),
			to_address=str(message.get("from_address") or ""),
			subject=subject,
			body=body,
		)
		self._store.update_action_send_status(action_id, "sent", "approved_and_sent")
		self._store.append_audit_log(
			action_id=action_id,
			message_id=message_id,
			event_type="sent",
			detail_json=json.dumps(
				{
					"provider_message_id": result.provider_message_id,
					"status": result.status,
					"sent_at": _utc_now(),
				},
				ensure_ascii=True,
			),
		)
		return {
			"action_id": action_id,
			"send_status": "sent",
			"provider_message_id": result.provider_message_id,
			"stub": os.environ.get("ADA_EMAIL_GMAIL_STUB", "1").strip().lower() not in {"0", "false", "no"},
		}
