from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ada.agent.llm import load_profile_from_env, make_llm_callable
from ada.email.attachment_store import AttachmentStore
from ada.email.gmail_client import build_gmail_client
from ada.email.gmail_sync import GmailSyncService
from ada.email.graph import run_email_draft, run_email_summarize
from ada.email.oauth_flow import GmailOAuthService
from ada.email.service import EmailConversationService
from ada.email.store import EmailStore
from ada.email.summary_skip import validate_summary_skip_rules
from ada.email.vault_tokens import GmailVaultTokens
from ada.heartbeat.runner import HeartbeatRunner
from ada.vault import VaultSession


DEFAULT_EMAIL_SETTINGS: dict[str, Any] = {
	"attachment_max_bytes": None,
	"inbox_poll_interval_sec": 30,
	"summary_skip_rules": [],
	"email_service_enabled": True,
	"email_graph_batch_size": 5,
	"gmail_backfill_max_messages": 50,
}


@dataclass
class EmailPlatform:
	store: EmailStore
	email_service: EmailConversationService
	attachment_store: AttachmentStore
	vault_tokens: GmailVaultTokens
	oauth_service: GmailOAuthService
	sync_service: GmailSyncService
	heartbeat: HeartbeatRunner
	_llm_callable: Callable[[list], str] | None = field(default=None, repr=False)

	@classmethod
	def from_env(cls) -> EmailPlatform:
		from ada.vault_unlock import bootstrap_vault_session

		return cls.from_session(bootstrap_vault_session())

	@classmethod
	def from_session(cls, session: VaultSession | None) -> EmailPlatform:
		db_env = os.environ.get("ADA_EMAIL_DB_PATH", "").strip()
		db_path = Path(db_env) if db_env else Path(__file__).resolve().parents[3] / "data" / "email_connector.sqlite3"
		store = EmailStore(db_path)
		store.ensure_default_tasks()
		if not store.get_email_settings():
			store.set_email_settings(dict(DEFAULT_EMAIL_SETTINGS))

		vault_tokens = GmailVaultTokens(session)
		email_service = EmailConversationService(store)
		attachment_store = AttachmentStore()
		oauth_service = GmailOAuthService(vault_tokens)

		platform = cls(
			store=store,
			email_service=email_service,
			attachment_store=attachment_store,
			vault_tokens=vault_tokens,
			oauth_service=oauth_service,
			sync_service=None,  # type: ignore[arg-type]
			heartbeat=None,  # type: ignore[arg-type]
		)

		def client_factory(account_id: str):
			return build_gmail_client(account_id, vault_tokens)

		def defer_reply(message_id: str) -> None:
			if store.get_task_enabled("gmail_reply_review"):
				platform.sync_service.enqueue_reply_review(message_id)

		sync_service = GmailSyncService(
			store,
			email_service,
			attachment_store,
			client_factory=client_factory,
			defer_reply_review=defer_reply,
		)
		platform.sync_service = sync_service
		platform.heartbeat = HeartbeatRunner(
			store=store,
			sync_service=sync_service,
			email_service=email_service,
			email_graph_fn=platform.process_email_graph_batch,
			vault_tokens=vault_tokens,
			client_factory=client_factory,
		)
		return platform

	def _llm_ready(self) -> bool:
		if self._llm_callable is None:
			try:
				profile = load_profile_from_env()
				self._llm_callable = make_llm_callable(profile)
			except Exception:
				return False
		return self._llm_callable is not None

	def _llm(self) -> Callable[[list], str]:
		if not self._llm_ready() or self._llm_callable is None:
			raise RuntimeError("LLM is not available for EmailGraph")
		return self._llm_callable

	def summarize_message(self, message_id: str) -> dict[str, Any]:
		message = self.store.get_message(message_id)
		if not message:
			raise KeyError(f"message not found: {message_id}")
		attachments = self.store.list_attachments(message_id)
		settings = self.get_email_settings()
		import json

		headers_raw = str(message.get("headers_json") or "{}")
		try:
			headers_obj = json.loads(headers_raw)
		except json.JSONDecodeError:
			headers_obj = {}
		state = {
			"message_id": message_id,
			"thread_id": str(message.get("thread_id") or ""),
			"account_id": str(message.get("account_id") or ""),
			"subject": str(message.get("subject") or ""),
			"body_text": str(message.get("body_text") or ""),
			"from_address": str(message.get("from_address") or ""),
			"attachment_names": [str(a.get("filename") or "") for a in attachments],
			"headers": headers_obj if isinstance(headers_obj, dict) else {},
			"summary_skip_rules": settings.get("summary_skip_rules") or [],
			"thread_snippet": None,
		}
		try:
			result = run_email_summarize(state, self._llm())
			todo_items = list(result.get("todo_items") or [])
			if todo_items:
				import json
				from datetime import UTC, datetime

				self.store.enqueue_deferred_task(
					"email_todo_push",
					json.dumps(
						{
							"source": "email_graph",
							"message_id": message_id,
							"thread_id": str(message.get("thread_id") or ""),
							"account_id": str(message.get("account_id") or ""),
							"todo_items": todo_items,
						},
						ensure_ascii=True,
					),
					datetime.now(UTC).isoformat(),
				)
			if result.get("should_summarize") is False:
				self.store.update_inbox_summary(
					message_id,
					summary_text="",
					summary_status="skipped",
				)
				return {"message_id": message_id, "summary_status": "skipped", "skip_rule_id": result.get("skip_rule_id")}
			self.store.update_inbox_summary(
				message_id,
				summary_text=str(result.get("summary_text") or ""),
				summary_status="ready",
			)
			return {"message_id": message_id, "summary_status": "ready"}
		except Exception:
			self.store.update_inbox_summary(
				message_id,
				summary_text="",
				summary_status="pending",
			)
			return {"message_id": message_id, "summary_status": "pending"}

	def process_email_graph_batch(self) -> dict[str, Any]:
		settings = self.get_email_settings()
		if not bool(settings.get("email_service_enabled", True)):
			return {"processed": 0, "skipped": True, "reason": "email_service_disabled"}
		limit = int(settings.get("email_graph_batch_size") or 5)
		limit = max(1, min(50, limit))
		processed = 0
		errors = 0
		for item in self.store.list_inbox_pending_summaries(limit=limit):
			message_id = str(item.get("message_id") or "")
			if not message_id:
				continue
			try:
				self.summarize_message(message_id)
				processed += 1
			except Exception:
				errors += 1
		return {"processed": processed, "errors": errors, "limit": limit}

	def draft_for_action(self, action_id: int, *, latest_user_message: str | None = None) -> dict[str, Any]:
		action = self.store.get_action(action_id)
		if not action:
			raise KeyError(f"action not found: {action_id}")
		message_id = str(action.get("message_id") or "")
		message = self.store.get_message(message_id)
		if not message:
			raise KeyError(f"message not found: {message_id}")
		state = {
			"message_id": message_id,
			"subject": str(message.get("subject") or ""),
			"body_text": latest_user_message or str(message.get("body_text") or ""),
			"from_address": str(message.get("from_address") or ""),
			"attachment_names": [],
			"thread_context": [{"from": message.get("from_address"), "body": message.get("body_text")}],
			"action_id": action_id,
		}
		result = run_email_draft(state, self._llm())
		return {
			"subject": str(result.get("draft_subject") or ""),
			"body": str(result.get("draft_body") or ""),
			"confidence": float(result.get("confidence") or 0.75),
			"safety_flags": list(result.get("safety_flags") or []),
		}

	def get_email_settings(self) -> dict[str, Any]:
		current = self.store.get_email_settings()
		merged = dict(DEFAULT_EMAIL_SETTINGS)
		merged.update(current)
		return merged

	def set_email_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
		if "summary_skip_rules" in payload:
			rules = payload.get("summary_skip_rules") or []
			if not isinstance(rules, list):
				raise ValueError("summary_skip_rules must be a list")
			payload["summary_skip_rules"] = validate_summary_skip_rules(rules)
		if "email_graph_batch_size" in payload:
			payload["email_graph_batch_size"] = max(1, min(50, int(payload["email_graph_batch_size"])))
		if "gmail_backfill_max_messages" in payload:
			payload["gmail_backfill_max_messages"] = max(1, min(100, int(payload["gmail_backfill_max_messages"])))
		if "email_service_enabled" in payload:
			payload["email_service_enabled"] = bool(payload["email_service_enabled"])
		current = self.get_email_settings()
		current.update(payload)
		self.store.set_email_settings(current)
		return current

	def connect_oauth_callback(self, *, code: str, state: str) -> dict[str, Any]:
		result = self.oauth_service.complete(code=code, state=state)
		account_id = str(result["account_id"])
		client = build_gmail_client(account_id, self.vault_tokens)
		profile = client.get_profile()
		email = str(profile.get("emailAddress") or "")
		self.store.upsert_account(account_id, email)
		self.store.set_account_status(account_id, "active", last_error=None)
		from ada.email.gmail_client import seed_history_id

		self.store.set_account_history_id(account_id, seed_history_id(client))
		self.sync_service.enqueue_backfill(account_id)
		return {"account_id": account_id, "email_address": email, "status": "active"}

	def test_account(self, account_id: str) -> dict[str, Any]:
		client = build_gmail_client(account_id, self.vault_tokens)
		profile = client.get_profile()
		return {"email_address": profile.get("emailAddress"), "history_id": profile.get("historyId")}
