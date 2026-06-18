from __future__ import annotations

import os
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from typing import Any
from dataclasses import dataclass

from ada.email.gmail_client import (
	GoogleGmailClient,
	tokens_to_dict,
)
from ada.email.gmail_sync import GmailSyncService
from ada.email.service import EmailConversationService
from ada.email.store import EmailStore
from ada.email.vault_tokens import GmailVaultTokens


def _utc_now() -> str:
	return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class HeartbeatCallback:
	id: str
	service: str
	fn: Callable[[], Any]


class HeartbeatRunner:
	def __init__(
		self,
		*,
		store: EmailStore,
		sync_service: GmailSyncService,
		email_service: EmailConversationService,
		email_graph_fn: Callable[[], dict[str, Any]],
		vault_tokens: GmailVaultTokens,
		client_factory: Callable[[str], GoogleGmailClient],
	) -> None:
		self._store = store
		self._sync_service = sync_service
		self._email_service = email_service
		self._email_graph_fn = email_graph_fn
		self._vault_tokens = vault_tokens
		self._client_factory = client_factory
		self._lock = threading.Lock()
		self._stop = threading.Event()
		self._thread: threading.Thread | None = None
		self._interval = self._load_interval_from_store(store)
		self._enabled = os.environ.get("ADA_HEARTBEAT_ENABLED", "1").strip().lower() not in {
			"0",
			"false",
			"no",
		}
		self._callbacks: list[HeartbeatCallback] = [
			HeartbeatCallback("gmail_token_refresh", "email", self._run_token_refresh),
			HeartbeatCallback("gmail_backfill", "email", self._run_gmail_backfill),
			HeartbeatCallback("gmail_sync", "email", self._run_gmail_sync),
			HeartbeatCallback("email_graph_run", "email", self._run_email_graph),
			HeartbeatCallback("gmail_reply_review", "email", self._run_reply_review),
			HeartbeatCallback("email_summary_to_chat", "email", self._run_summary_to_chat),
		]

	@staticmethod
	def _load_interval_from_store(store: EmailStore) -> int:
		sys_settings = store.get_system_settings()
		db_val = sys_settings.get("heartbeat_interval_sec")
		if isinstance(db_val, int) and db_val >= 5:
			return db_val
		return int(os.environ.get("ADA_HEARTBEAT_INTERVAL_SEC", "60"))

	def start(self) -> None:
		if not self._enabled or self._thread is not None:
			return
		self._store.ensure_default_tasks()
		self._thread = threading.Thread(target=self._loop, name="ada-heartbeat", daemon=True)
		self._thread.start()

	def stop(self) -> None:
		self._stop.set()
		if self._thread is not None:
			self._thread.join(timeout=5)
			self._thread = None

	def tick(self) -> dict[str, Any]:
		if not self._lock.acquire(blocking=False):
			return {"skipped": True, "reason": "lock_busy"}
		started = _utc_now()
		status = "ok"
		error: str | None = None
		results: dict[str, Any] = {}
		try:
			results = self._run_registered_callbacks()
		except Exception as exc:
			status = "error"
			error = str(exc)
		finally:
			self._lock.release()
		finished = _utc_now()
		self._store.record_heartbeat_run(
			started_at=started,
			finished_at=finished,
			status=status,
			error=error,
		)
		return {"status": status, "error": error, "results": results}

	def _service_enabled(self, service: str) -> bool:
		if service != "email":
			return True
		settings = self._store.get_email_settings()
		return bool(settings.get("email_service_enabled", True))

	def _run_registered_callbacks(self) -> dict[str, Any]:
		results: dict[str, Any] = {}
		for callback in self._callbacks:
			if not self._service_enabled(callback.service):
				results[callback.id] = {"skipped": True, "reason": f"{callback.service}_service_disabled"}
				continue
			if not self._store.get_task_enabled(callback.id):
				results[callback.id] = {"skipped": True, "reason": "task_disabled"}
				continue
			try:
				results[callback.id] = callback.fn()
			except Exception as exc:
				results[callback.id] = {"error": str(exc)}
		return results

	def settings_payload(self) -> dict[str, Any]:
		last = self._store.get_last_heartbeat_run()
		next_run = None
		if last and last.get("finished_at"):
			try:
				finished = datetime.fromisoformat(str(last["finished_at"]))
				next_run = (finished + timedelta(seconds=self._interval)).isoformat()
			except ValueError:
				next_run = None
		return {
			"interval_sec": self._interval,
			"enabled": self._enabled,
			"tasks": self._store.list_task_settings(),
			"last_run_at": last.get("finished_at") if last else None,
			"next_run_at": next_run,
		}

	def update_interval(self, interval_sec: int) -> None:
		self._interval = max(5, int(interval_sec))
		self._store.set_system_settings({"heartbeat_interval_sec": self._interval})

	def _loop(self) -> None:
		while not self._stop.is_set():
			self.tick()
			self._stop.wait(self._interval)

	def _run_gmail_sync(self) -> list[dict[str, Any]]:
		out: list[dict[str, Any]] = []
		for account in self._store.list_active_accounts():
			account_id = str(account["id"])
			self._sync_service.maybe_enqueue_backfill_if_empty(account_id)
			out.append(self._sync_service.sync_account(account_id))
		return out

	def _run_gmail_backfill(self) -> list[dict[str, Any]]:
		import json

		out: list[dict[str, Any]] = []
		for item in self._store.list_pending_deferred_tasks("gmail_backfill"):
			try:
				payload = json.loads(str(item.get("payload_json") or "{}"))
			except json.JSONDecodeError:
				self._store.mark_deferred_processed(int(item["id"]), _utc_now())
				continue
			account_id = str(payload.get("account_id") or "")
			if not account_id:
				self._store.mark_deferred_processed(int(item["id"]), _utc_now())
				continue
			try:
				result = self._sync_service.backfill_recent(account_id)
				out.append(result)
			except Exception as exc:
				out.append({"account_id": account_id, "error": str(exc)})
			self._store.mark_deferred_processed(int(item["id"]), _utc_now())
		return out

	def _run_token_refresh(self) -> list[dict[str, Any]]:
		out: list[dict[str, Any]] = []
		if not self._vault_tokens.is_configured():
			return out
		for account in self._store.list_accounts():
			account_id = str(account["id"])
			if str(account.get("status")) == "auth_error":
				continue
			try:
				client = self._client_factory(account_id)
				tokens = client.refresh()
				self._vault_tokens.save_account_tokens(account_id, tokens_to_dict(tokens))
				out.append({"account_id": account_id, "refreshed": True})
			except Exception as exc:
				self._store.set_account_status(account_id, "auth_error", last_error=str(exc))
				out.append({"account_id": account_id, "refreshed": False, "error": str(exc)})
		return out

	def _run_email_graph(self) -> dict[str, Any]:
		return self._email_graph_fn()

	def _run_reply_review(self) -> list[dict[str, Any]]:
		out: list[dict[str, Any]] = []
		for item in self._store.list_pending_deferred_tasks("gmail_reply_review"):
			import json
			payload = json.loads(str(item["payload_json"]))
			message_id = str(payload.get("message_id") or "")
			if message_id:
				result = self._email_service.process_message(message_id)
				out.append({"message_id": message_id, "action_id": result.get("action_id")})
			self._store.mark_deferred_processed(int(item["id"]), _utc_now())
		return out

	def _run_summary_to_chat(self) -> list[dict[str, Any]]:
		out: list[dict[str, Any]] = []
		now = _utc_now()
		for item in self._store.list_inbox_for_delivery():
			self._store.mark_inbox_delivered(int(item["id"]), now)
			out.append({"inbox_id": int(item["id"]), "message_id": item["message_id"]})
		return out


class HeartbeatLifecycle(AbstractContextManager["HeartbeatRunner"]):
	def __init__(self, runner: HeartbeatRunner) -> None:
		self._runner = runner

	def __enter__(self) -> HeartbeatRunner:
		self._runner.start()
		return self._runner

	def __exit__(self, *args: object) -> None:
		self._runner.stop()
