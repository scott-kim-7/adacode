from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ada.agent.server import create_app
from ada.email.auth import configure_local_api_key
from ada.email.platform import EmailPlatform

TEST_API_KEY = "test-local-api-key"


def _email_env(db_path: Path) -> dict[str, str]:
	return {
		"ADA_EMAIL_DB_PATH": str(db_path),
		"ADA_HEARTBEAT_ENABLED": "0",
	}


def _auth_headers() -> dict[str, str]:
	return {"X-Ada-Local-Key": TEST_API_KEY}


def _client(db_path: Path) -> TestClient:
	configure_local_api_key(TEST_API_KEY)
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		platform = EmailPlatform.from_session(None)
		return TestClient(create_app(email_platform=platform))


def _seed_message(client: TestClient, message_id: str) -> None:
	payload = {
		"message": {
			"account_id": "acct-1",
			"account_email": "ada@example.com",
			"message_id": message_id,
			"thread_id": f"thread-{message_id}",
			"subject": f"Ada {message_id}",
			"body_text": "Ada, 확인 부탁",
			"from_address": "user@example.com",
			"to_addresses": ["ada@example.com"],
			"headers": {},
			"participants": ["user@example.com", "ada@example.com"],
			"attachments": [],
		}
	}
	resp = client.post("/ingest/gmail/webhook", json=payload, headers=_auth_headers())
	assert resp.status_code == 200


def test_email_messages_list_and_detail(tmp_path: Path):
	client = _client(tmp_path / "email.sqlite3")
	_seed_message(client, "msg-a")
	list_resp = client.get("/email/messages", headers=_auth_headers())
	assert list_resp.status_code == 200
	body = list_resp.json()
	assert body["total"] >= 1
	message_id = body["data"][0]["message_id"]
	detail = client.get(f"/email/messages/{message_id}", headers=_auth_headers())
	assert detail.status_code == 200
	assert detail.json()["message_id"] == message_id


def test_email_bulk_read_by_ids(tmp_path: Path):
	client = _client(tmp_path / "email.sqlite3")
	_seed_message(client, "msg-b")
	_seed_message(client, "msg-c")
	rows = client.get("/email/messages?read_status=unread", headers=_auth_headers()).json()["data"]
	ids = [r["inbox_id"] for r in rows if r.get("inbox_id") is not None][:2]
	resp = client.post("/email/inbox/read-bulk", json={"inbox_ids": ids}, headers=_auth_headers())
	assert resp.status_code == 200
	assert resp.json()["updated"] >= 1


def _seed_delivered_inbox(client: TestClient, platform: EmailPlatform, message_id: str) -> int:
	from datetime import UTC, datetime

	_seed_message(client, message_id)
	rows = client.get("/email/messages", headers=_auth_headers()).json()["data"]
	inbox_id = int(next(r["inbox_id"] for r in rows if r["message_id"] == message_id))
	platform.store.update_inbox_summary(message_id, summary_text="summary", summary_status="ready")
	platform.store.mark_inbox_delivered(inbox_id, datetime.now(UTC).isoformat())
	return inbox_id


def test_email_read_all_delivered_inbox(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		platform = EmailPlatform.from_session(None)
		client = TestClient(create_app(email_platform=platform))
		_seed_delivered_inbox(client, platform, "msg-d1")
		_seed_delivered_inbox(client, platform, "msg-d2")
		resp = client.post("/email/inbox/read-all", headers=_auth_headers())
		assert resp.status_code == 200
		assert resp.json()["updated"] == 2
		again = client.post("/email/inbox/read-all", headers=_auth_headers())
		assert again.json()["updated"] == 0
		visible = client.get("/email/inbox?visible=1&since_id=0", headers=_auth_headers())
		assert visible.status_code == 200
		assert visible.json()["data"] == []
