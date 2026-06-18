from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ada.agent.server import create_app
from ada.email.auth import configure_local_api_key
from ada.email.platform import EmailPlatform
from ada.email.policy import evaluate_reply_policy

TEST_API_KEY = "test-local-api-key"


def _email_env(db_path: Path) -> dict[str, str]:
	return {
		"ADA_EMAIL_DB_PATH": str(db_path),
		"ADA_HEARTBEAT_ENABLED": "0",
	}


def _auth_headers() -> dict[str, str]:
	return {"X-Ada-Local-Key": TEST_API_KEY}


def _test_client(db_path: Path) -> TestClient:
	configure_local_api_key(TEST_API_KEY)
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		platform = EmailPlatform.from_session(None)
		return TestClient(create_app(email_platform=platform))


def test_trusted_proxy_auth_without_api_key(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	configure_local_api_key(TEST_API_KEY)
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		platform = EmailPlatform.from_session(None)
		client = TestClient(create_app(email_platform=platform))
		with patch("ada.email.auth._client_ip", return_value="172.17.0.2"):
			resp = client.get(
				"/ops/email/oauth-readiness",
				headers={"X-Ada-WebUI-Proxy": "1"},
			)
		assert resp.status_code == 200


def test_reply_policy_requires_mention_and_request():
	decision = evaluate_reply_policy(
		subject="질문",
		body="Ada, 이 메일에 회신 부탁해",
		sender="user@example.com",
		headers={},
	)
	assert decision.detected_mention is True
	assert decision.detected_reply_intent is True
	assert decision.allowed_to_reply is True
	assert decision.reason == "policy_passed"


def test_reply_policy_blocks_without_reply_intent():
	decision = evaluate_reply_policy(
		subject="Ada 참고",
		body="상황만 공유할게",
		sender="user@example.com",
		headers={},
	)
	assert decision.detected_mention is True
	assert decision.detected_reply_intent is False
	assert decision.allowed_to_reply is False
	assert decision.reason == "reply_intent_missing"


def test_reply_policy_blocks_noreply_sender():
	decision = evaluate_reply_policy(
		subject="Ada please reply",
		body="reply please",
		sender="noreply@service.example",
		headers={},
	)
	assert decision.allowed_to_reply is False
	assert decision.reason == "noreply_sender"


def test_reply_policy_blocks_list_id_header():
	decision = evaluate_reply_policy(
		subject="Ada please reply",
		body="reply please",
		sender="user@example.com",
		headers={"List-Id": "<list.example.com>"},
	)
	assert decision.allowed_to_reply is False
	assert decision.reason == "mailing_list_message"


def test_oauth_readiness_reports_missing_vault(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		client = _test_client(db_path)
		resp = client.get("/ops/email/oauth-readiness", headers=_auth_headers())
		assert resp.status_code == 200
		body = resp.json()
		assert body["ready"] is False
		assert len(body["steps"]) >= 1
		assert body["agent_port"] == 9082
		assert body["redirect_uri"] == "http://127.0.0.1:9082/oauth/gmail/callback"

		start = client.get("/oauth/gmail/start", headers=_auth_headers())
		assert start.status_code == 503
		assert "vault" in start.json()["detail"].lower()


def test_webhook_requires_local_api_key(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		client = _test_client(db_path)
		resp = client.post("/ingest/gmail/webhook", json={"message": _sample_message()})
		assert resp.status_code == 401


def test_webhook_rejects_storage_uri(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		client = _test_client(db_path)
		payload = _sample_message()
		payload["attachments"] = [
			{
				"filename": "screen.png",
				"mime_type": "image/png",
				"size_bytes": 1234,
				"storage_uri": "s3://bucket/screen.png",
			}
		]
		resp = client.post("/ingest/gmail/webhook", json={"message": payload}, headers=_auth_headers())
		assert resp.status_code == 400


def test_settings_reject_invalid_summary_skip_rules(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		client = _test_client(db_path)
		resp = client.put(
			"/ops/email/settings",
			json={"summary_skip_rules": [{"id": "r1", "name": "bad", "match": "sender_domain"}]},
			headers=_auth_headers(),
		)
		assert resp.status_code == 422


def test_email_service_off_skips_webhook_queue_push(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		client = _test_client(db_path)
		headers = _auth_headers()
		set_resp = client.put("/ops/email/settings", json={"email_service_enabled": False}, headers=headers)
		assert set_resp.status_code == 200
		resp = client.post("/ingest/gmail/webhook", json={"message": _sample_message()}, headers=headers)
		assert resp.status_code == 200
		assert resp.json().get("skipped") is True


def test_process_message_is_idempotent(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path), clear=False):
		client = _test_client(db_path)
		headers = _auth_headers()
		client.post("/ingest/gmail/webhook", json={"message": _sample_message()}, headers=headers)
		first = client.post("/process/message/msg-1", headers=headers)
		second = client.post("/process/message/msg-1", headers=headers)
		assert first.status_code == 200
		assert second.status_code == 200
		assert first.json()["action_id"] == second.json()["action_id"]
		list_resp = client.get("/ops/email/actions?status=pending_review", headers=headers)
		assert len(list_resp.json()["data"]) == 1


def test_email_endpoints_ingest_process_and_list_pending(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path)):
		client = _test_client(db_path)
		headers = _auth_headers()
		ingest_resp = client.post(
			"/ingest/gmail/webhook",
			json={"message": _sample_message()},
			headers=headers,
		)
		assert ingest_resp.status_code == 200
		assert ingest_resp.json()["inserted"] is True

		process_resp = client.post("/process/message/msg-1", headers=headers)
		assert process_resp.status_code == 200
		body = process_resp.json()
		assert body["allowed_to_reply"] is True
		assert body["send_status"] == "pending_review"

		list_resp = client.get("/ops/email/actions?status=pending_review", headers=headers)
		assert list_resp.status_code == 200
		data = list_resp.json()["data"]
		assert len(data) == 1
		assert data[0]["message_id"] == "msg-1"


def test_agent_email_draft_requires_action_id(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path)):
		client = _test_client(db_path)
		headers = _auth_headers()
		resp = client.post("/agent/email/draft", json={"thread_context": []}, headers=headers)
		assert resp.status_code == 400

		client.post("/ingest/gmail/webhook", json={"message": _sample_message()}, headers=headers)
		process = client.post("/process/message/msg-1", headers=headers)
		action_id = process.json()["action_id"]

		with patch("ada.email.platform.run_email_draft") as mock_draft:
			mock_draft.return_value = {
				"draft_subject": "Re: 문의",
				"draft_body": "일정 업데이트해줘",
				"confidence": 0.75,
				"safety_flags": [],
			}
			ok = client.post(
				"/agent/email/draft",
				json={
					"action_id": action_id,
					"latest_user_message": "일정 업데이트해줘",
					"thread_context": [{"from": "user@example.com", "body": "안내 부탁"}],
				},
				headers=headers,
			)
		assert ok.status_code == 200
		payload = ok.json()
		assert payload["subject"] == "Re: 문의"
		assert "일정 업데이트해줘" in payload["body"]


def test_approve_send_transitions_action_to_sent(tmp_path: Path):
	db_path = tmp_path / "email.sqlite3"
	with patch.dict("os.environ", _email_env(db_path)):
		client = _test_client(db_path)
		headers = _auth_headers()
		client.post(
			"/ingest/gmail/webhook",
			json={
				"message": {
					"account_id": "acct-1",
					"account_email": "ada@example.com",
					"message_id": "msg-2",
					"thread_id": "thread-2",
					"subject": "Ada 요청",
					"body_text": "Ada please reply to this",
					"from_address": "user@example.com",
					"to_addresses": ["ada@example.com"],
					"headers": {},
					"participants": ["user@example.com", "ada@example.com"],
				}
			},
			headers=headers,
		)
		process = client.post("/process/message/msg-2", headers=headers)
		action_id = process.json()["action_id"]
		approve = client.post(
			f"/ops/email/actions/{action_id}/approve-send",
			json={"subject": "Re: Ada 요청", "body": "확인했습니다."},
			headers=headers,
		)
		assert approve.status_code == 200
		payload = approve.json()
		assert payload["send_status"] == "sent"
		assert payload["stub"] is True

		again = client.post(
			f"/ops/email/actions/{action_id}/approve-send",
			json={"subject": "Re: Ada 요청", "body": "재전송"},
			headers=headers,
		)
		assert again.status_code == 409


def _sample_message() -> dict[str, object]:
	return {
		"account_id": "acct-1",
		"account_email": "ada@example.com",
		"message_id": "msg-1",
		"thread_id": "thread-1",
		"subject": "Ada 도움 요청",
		"body_text": "Ada, 이 내용 확인하고 회신 부탁해",
		"from_address": "user@example.com",
		"to_addresses": ["ada@example.com"],
		"headers": {},
		"participants": ["user@example.com", "ada@example.com"],
		"attachments": [],
	}
