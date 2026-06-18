from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

from ada.email.attachment_store import AttachmentStore
from ada.email.gmail_sync import GmailSyncService
from ada.email.platform import EmailPlatform
from ada.email.service import EmailConversationService
from ada.email.store import EmailStore


def _gmail_not_found() -> HttpError:
	resp = MagicMock()
	resp.status = 404
	return HttpError(resp, b'{"error": {"message": "Requested entity was not found."}}')


def _minimal_gmail_message(message_id: str) -> dict:
	return {
		"id": message_id,
		"threadId": f"thread-{message_id}",
		"payload": {
			"headers": [
				{"name": "From", "value": "sender@example.com"},
				{"name": "Subject", "value": "Hello"},
				{"name": "To", "value": "ada@example.com"},
			],
			"mimeType": "text/plain",
			"body": {"data": "SGVsbG8="},
		},
	}


def test_gmail_sync_seeds_history_id(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	store = EmailStore(db_path)
	store.upsert_account("acct-1", "ada@example.com")
	email_service = EmailConversationService(store)
	attachment_store = AttachmentStore()

	client = MagicMock()
	client.list_history.side_effect = AssertionError("should seed first")
	client.list_latest_message_id.return_value = None
	client.get_profile.return_value = {"historyId": "12345"}

	def factory(account_id: str):
		return client

	sync = GmailSyncService(store, email_service, attachment_store, client_factory=factory)
	result = sync.sync_account("acct-1")
	assert result["seeded"] is True
	assert store.get_account("acct-1")["gmail_history_id"] == "12345"


def test_gmail_sync_skips_deleted_message_and_advances_history(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	store = EmailStore(db_path)
	store.upsert_account("acct-1", "ada@example.com")
	store.set_account_history_id("acct-1", "1000")
	email_service = EmailConversationService(store)
	attachment_store = AttachmentStore()

	client = MagicMock()
	client.list_history.return_value = {
		"historyId": "2000",
		"history": [
			{
				"messagesAdded": [
					{"message": {"id": "deleted-msg"}},
					{"message": {"id": "live-msg"}},
				]
			}
		],
	}

	def get_raw_message(message_id: str) -> bytes:
		if message_id == "deleted-msg":
			raise _gmail_not_found()
		return b"raw"

	client.get_raw_message.side_effect = get_raw_message
	client.get_message.return_value = _minimal_gmail_message("live-msg")
	client.get_attachment.return_value = b""

	def factory(account_id: str):
		return client

	sync = GmailSyncService(store, email_service, attachment_store, client_factory=factory)
	result = sync.sync_account("acct-1")

	assert result["processed"] == 1
	assert result["skipped_deleted"] == 1
	assert result["history_id"] == "2000"
	assert store.get_account("acct-1")["gmail_history_id"] == "2000"
	assert store.get_message("deleted-msg") is None
	assert store.get_message("live-msg") is not None


def test_heartbeat_tick_runs_gmail_sync(tmp_path: Path, monkeypatch):
	monkeypatch.setenv("ADA_EMAIL_DB_PATH", str(tmp_path / "email.sqlite3"))
	monkeypatch.setenv("ADA_HEARTBEAT_ENABLED", "0")
	platform = EmailPlatform.from_session(None)
	platform.store.upsert_account("acct-1", "ada@example.com")

	with patch.object(platform.sync_service, "sync_account", return_value={"processed": 0}) as mock_sync:
		result = platform.heartbeat.tick()
	assert result["status"] == "ok"
	mock_sync.assert_called_once_with("acct-1")


def test_email_settings_defaults(tmp_path: Path, monkeypatch):
	monkeypatch.setenv("ADA_EMAIL_DB_PATH", str(tmp_path / "email.sqlite3"))
	monkeypatch.setenv("ADA_HEARTBEAT_ENABLED", "0")
	platform = EmailPlatform.from_session(None)
	settings = platform.get_email_settings()
	assert settings["inbox_poll_interval_sec"] == 30
	assert settings["attachment_max_bytes"] is None
	assert settings["gmail_backfill_max_messages"] == 50


def test_backfill_recent_ingests_messages(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	store = EmailStore(db_path)
	store.upsert_account("acct-1", "ada@example.com")
	email_service = EmailConversationService(store)
	attachment_store = AttachmentStore()

	client = MagicMock()
	client.list_recent_message_ids.return_value = ["msg-1", "msg-2"]
	client.get_raw_message.return_value = b"raw"
	client.get_message.return_value = {
		"id": "msg-1",
		"threadId": "thread-1",
		"payload": {
			"headers": [
				{"name": "From", "value": "sender@example.com"},
				{"name": "Subject", "value": "Hello"},
				{"name": "To", "value": "ada@example.com"},
			],
			"mimeType": "text/plain",
			"body": {"data": "SGVsbG8="},
		},
	}
	client.get_attachment.return_value = b""

	def factory(account_id: str):
		return client

	sync = GmailSyncService(store, email_service, attachment_store, client_factory=factory)
	result = sync.backfill_recent("acct-1", max_results=2)
	assert result["backfilled"] == 2
	assert store.count_messages({"account_id": "acct-1"}) == 2


def test_heartbeat_runs_gmail_backfill_deferred_task(tmp_path: Path, monkeypatch):
	monkeypatch.setenv("ADA_EMAIL_DB_PATH", str(tmp_path / "email.sqlite3"))
	monkeypatch.setenv("ADA_HEARTBEAT_ENABLED", "0")
	platform = EmailPlatform.from_session(None)
	platform.store.upsert_account("acct-1", "ada@example.com")
	platform.sync_service.enqueue_backfill("acct-1")

	with patch.object(platform.sync_service, "backfill_recent", return_value={"backfilled": 1}) as mock_backfill:
		result = platform.heartbeat.tick()

	assert mock_backfill.called
	assert result["status"] == "ok"
	assert "gmail_backfill" in result["results"]


def test_heartbeat_interval_persists(tmp_path: Path, monkeypatch):
	monkeypatch.setenv("ADA_EMAIL_DB_PATH", str(tmp_path / "email.sqlite3"))
	monkeypatch.setenv("ADA_HEARTBEAT_ENABLED", "0")
	platform = EmailPlatform.from_session(None)
	platform.heartbeat.update_interval(120)
	assert platform.store.get_system_settings()["heartbeat_interval_sec"] == 120
	platform2 = EmailPlatform.from_session(None)
	assert platform2.heartbeat.settings_payload()["interval_sec"] == 120
