from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ada.email.auth import require_email_auth
from ada.email.platform import EmailPlatform
from ada.email.service import GmailAttachment, IngestedMessage
from ada.email.vault_tokens import GOOGLE_OAUTH_CREDENTIALS_URL
from ada.ports import agent_port, gmail_oauth_redirect_uri
from ada.vault import VaultError


def _default_received_at() -> str:
	return datetime.now(UTC).isoformat()


class AttachmentIn(BaseModel):
	filename: str
	mime_type: str
	size_bytes: int = 0
	storage_uri: str = ""


class GmailMessageIn(BaseModel):
	account_id: str = Field(default="default")
	account_email: str
	message_id: str
	thread_id: str
	subject: str = ""
	body_text: str = ""
	from_address: str
	to_addresses: list[str] = Field(default_factory=list)
	headers: dict[str, str] = Field(default_factory=dict)
	participants: list[str] = Field(default_factory=list)
	received_at: str = Field(default_factory=_default_received_at)
	attachments: list[AttachmentIn] = Field(default_factory=list)


class WebhookIn(BaseModel):
	message: GmailMessageIn


class ProcessMessageResult(BaseModel):
	action_id: int
	message_id: str
	detected_mention: bool
	detected_reply_intent: bool
	allowed_to_reply: bool
	reason: str
	draft_status: str
	send_status: str


class ApproveSendRequest(BaseModel):
	subject: str
	body: str


class EmailSettingsIn(BaseModel):
	attachment_max_bytes: int | None = None
	inbox_poll_interval_sec: int | None = None
	email_service_enabled: bool | None = None
	email_graph_batch_size: int | None = Field(default=None, ge=1, le=50)
	summary_skip_rules: list[dict[str, Any]] | None = None


class HeartbeatSettingsIn(BaseModel):
	tasks: dict[str, bool] | None = None
	interval_sec: int | None = Field(default=None, ge=5, le=3600)


class MessageSearchParams(BaseModel):
	q: str | None = None
	account_id: str | None = None
	read_status: str = "all"
	has_attachment: bool | None = None
	summary_status: str = "all"
	date_from: str | None = None
	date_to: str | None = None
	sort: str = "received_at"
	order: str = "desc"
	limit: int = Field(default=50, ge=1, le=100)
	offset: int = Field(default=0, ge=0)


class ReadBulkIn(BaseModel):
	inbox_ids: list[int] | None = None
	filter: MessageSearchParams | None = None


class OAuthClientIn(BaseModel):
	client_id: str
	client_secret: str


def _reject_external_attachment_uris(attachments: list[AttachmentIn]) -> None:
	for item in attachments:
		if item.storage_uri.strip():
			raise HTTPException(
				status_code=400,
				detail="storage_uri ingest is not supported via webhook until local attachment storage is enabled",
			)


def build_email_router(
	platform: EmailPlatform | None = None,
	*,
	allowed_domains: tuple[str, ...] | None = None,
) -> APIRouter:
	router = APIRouter(tags=["email"], dependencies=[Depends(require_email_auth)])
	email_platform = platform or EmailPlatform.from_env()
	email_service = email_platform.email_service

	@router.post("/ingest/gmail/webhook")
	async def ingest_gmail_webhook(payload: WebhookIn) -> dict[str, Any]:
		settings = email_platform.get_email_settings()
		if not bool(settings.get("email_service_enabled", True)):
			return {"inserted": False, "skipped": True, "reason": "email_service_disabled"}
		message = payload.message
		_reject_external_attachment_uris(message.attachments)
		record = IngestedMessage(
			account_id=message.account_id,
			account_email=message.account_email,
			message_id=message.message_id,
			thread_id=message.thread_id,
			subject=message.subject,
			body_text=message.body_text,
			from_address=message.from_address,
			to_addresses=message.to_addresses,
			headers=message.headers,
			participants=message.participants or [message.from_address, *message.to_addresses],
			received_at=message.received_at,
			attachments=tuple(
				GmailAttachment(
					filename=item.filename,
					mime_type=item.mime_type,
					size_bytes=item.size_bytes,
					storage_uri=item.storage_uri,
				)
				for item in message.attachments
			),
		)
		result = email_service.ingest_message(record)
		if result.get("inserted"):
			email_platform.store.insert_inbox_item(
				message_id=message.message_id,
				thread_id=message.thread_id,
				summary_status="pending",
			)
		return result

	@router.post("/process/message/{gmail_message_id}", response_model=ProcessMessageResult)
	async def process_message(gmail_message_id: str) -> ProcessMessageResult:
		try:
			result = email_service.process_message(
				gmail_message_id,
				allowed_domains=allowed_domains,
			)
		except KeyError as exc:
			raise HTTPException(status_code=404, detail=str(exc)) from exc
		return ProcessMessageResult(**result)

	@router.get("/ops/email/actions")
	async def list_actions(status: str = "pending_review") -> dict[str, Any]:
		if status != "pending_review":
			return {"data": [], "status": status}
		return {"data": email_service.list_pending_reviews(), "status": status}

	@router.post("/agent/email/draft")
	async def create_email_draft(payload: dict[str, Any]) -> dict[str, Any]:
		latest = str(payload.get("latest_user_message") or "").strip()
		action_id = payload.get("action_id")
		if action_id is not None:
			try:
				return email_platform.draft_for_action(int(action_id), latest_user_message=latest or None)
			except KeyError as exc:
				raise HTTPException(status_code=404, detail=str(exc)) from exc
			except RuntimeError as exc:
				raise HTTPException(status_code=503, detail=str(exc)) from exc
		if not latest:
			raise HTTPException(status_code=400, detail="latest_user_message or action_id is required")
		raise HTTPException(status_code=400, detail="action_id is required for EmailGraph draft")

	@router.post("/ops/email/actions/{action_id}/approve-send")
	async def approve_send(action_id: int, payload: ApproveSendRequest) -> dict[str, Any]:
		try:
			return email_service.approve_and_send(action_id, subject=payload.subject, body=payload.body)
		except KeyError as exc:
			raise HTTPException(status_code=404, detail=str(exc)) from exc
		except ValueError as exc:
			raise HTTPException(status_code=409, detail=str(exc)) from exc

	@router.get("/ops/email/oauth-readiness")
	async def oauth_readiness() -> dict[str, Any]:
		readiness = email_platform.vault_tokens.oauth_readiness()
		redirect = gmail_oauth_redirect_uri()
		return {
			"ready": readiness.ready,
			"vault_file": readiness.vault_file,
			"vault_unlocked": readiness.vault_unlocked,
			"gmail_client": readiness.gmail_client,
			"gmail_client_status": readiness.gmail_client_status,
			"steps": list(readiness.steps),
			"redirect_uri": redirect,
			"agent_port": agent_port(),
			"google_console_credentials_url": GOOGLE_OAUTH_CREDENTIALS_URL,
			"redirect_uri_mismatch_hint": (
				"If Google shows redirect_uri_mismatch, add the redirect_uri above to your "
				"OAuth client's Authorized redirect URIs (port changed from 8082 to 9082)."
			),
		}

	@router.put("/ops/email/oauth-client")
	async def put_oauth_client(payload: OAuthClientIn) -> dict[str, Any]:
		try:
			email_platform.vault_tokens.save_client_credentials(
				payload.client_id,
				payload.client_secret,
			)
		except VaultError as exc:
			raise HTTPException(status_code=503, detail=str(exc)) from exc
		readiness = email_platform.vault_tokens.oauth_readiness()
		return {
			"saved": True,
			"ready": readiness.ready,
			"gmail_client_status": readiness.gmail_client_status,
		}

	@router.get("/oauth/gmail/start")
	async def oauth_gmail_start(account_id: str | None = None) -> dict[str, str]:
		try:
			result = email_platform.oauth_service.start(account_id=account_id)
			result["redirect_uri"] = gmail_oauth_redirect_uri()
			return result
		except RuntimeError as exc:
			raise HTTPException(status_code=503, detail=str(exc)) from exc

	@router.get("/oauth/gmail/callback")
	async def oauth_gmail_callback(code: str, state: str) -> dict[str, Any]:
		try:
			return email_platform.connect_oauth_callback(code=code, state=state)
		except ValueError as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc
		except Exception as exc:
			raise HTTPException(status_code=502, detail=str(exc)) from exc

	@router.get("/ops/email/accounts")
	async def list_accounts() -> dict[str, Any]:
		return {"data": email_platform.store.list_accounts()}

	@router.delete("/ops/email/accounts/{account_id}")
	async def delete_account(account_id: str) -> dict[str, Any]:
		email_platform.vault_tokens.delete_account_tokens(account_id)
		deleted = email_platform.store.delete_account(account_id)
		return {"deleted": deleted, "account_id": account_id}

	@router.post("/ops/email/accounts/{account_id}/test")
	async def test_account(account_id: str) -> dict[str, Any]:
		try:
			return email_platform.test_account(account_id)
		except Exception as exc:
			raise HTTPException(status_code=502, detail=str(exc)) from exc

	@router.get("/ops/email/settings")
	async def get_email_settings() -> dict[str, Any]:
		return email_platform.get_email_settings()

	@router.put("/ops/email/settings")
	async def put_email_settings(payload: EmailSettingsIn) -> dict[str, Any]:
		updates = payload.model_dump(exclude_unset=True)
		try:
			return email_platform.set_email_settings(updates)
		except ValueError as exc:
			raise HTTPException(status_code=422, detail=str(exc)) from exc

	@router.get("/ops/heartbeat/settings")
	async def get_heartbeat_settings() -> dict[str, Any]:
		return email_platform.heartbeat.settings_payload()

	@router.put("/ops/heartbeat/settings")
	async def put_heartbeat_settings(payload: HeartbeatSettingsIn) -> dict[str, Any]:
		if payload.interval_sec is not None:
			email_platform.heartbeat.update_interval(payload.interval_sec)
		if payload.tasks:
			for task_id, enabled in payload.tasks.items():
				email_platform.store.set_task_enabled(task_id, enabled)
		return email_platform.heartbeat.settings_payload()

	@router.post("/ops/heartbeat/tick")
	async def heartbeat_tick() -> dict[str, Any]:
		return email_platform.heartbeat.tick()

	@router.get("/email/inbox")
	async def list_inbox(
		visible: int | None = None,
		since_id: int = Query(default=0),
	) -> dict[str, Any]:
		if visible == 1:
			rows = email_platform.store.list_inbox_visible(since_id=since_id)
		else:
			rows = email_platform.store.list_inbox_for_delivery()
		data = [
			{
				"id": row["id"],
				"message_id": row["message_id"],
				"thread_id": row["thread_id"],
				"subject": row.get("subject"),
				"from_address": row.get("from_address"),
				"received_at": row.get("received_at"),
				"summary_text": row.get("summary_text"),
				"summary_status": row.get("summary_status"),
				"delivered_at": row.get("delivered_at"),
			}
			for row in rows
		]
		next_since = max((int(item["id"]) for item in data), default=since_id)
		return {"data": data, "next_since_id": next_since}

	@router.post("/email/inbox/{inbox_id}/read")
	async def mark_inbox_read(inbox_id: int) -> dict[str, Any]:
		ok = email_platform.store.mark_inbox_read(inbox_id, datetime.now(UTC).isoformat())
		if not ok:
			raise HTTPException(status_code=404, detail="inbox item not found")
		return {"id": inbox_id, "read": True}

	@router.post("/email/inbox/read-bulk")
	async def mark_inbox_read_bulk(payload: ReadBulkIn) -> dict[str, Any]:
		try:
			updated = email_platform.store.mark_inbox_read_bulk(
				inbox_ids=payload.inbox_ids,
				filters=payload.filter.model_dump(exclude_none=True) if payload.filter else None,
				read_at=datetime.now(UTC).isoformat(),
			)
		except ValueError as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc
		return {"updated": updated}

	@router.post("/email/inbox/read-all")
	async def mark_all_inbox_read() -> dict[str, Any]:
		updated = email_platform.store.mark_all_inbox_delivered_read(datetime.now(UTC).isoformat())
		return {"updated": updated}

	@router.get("/email/messages")
	async def list_messages(
		q: str | None = None,
		account_id: str | None = None,
		read_status: str = "all",
		has_attachment: bool | None = None,
		summary_status: str = "all",
		date_from: str | None = None,
		date_to: str | None = None,
		sort: str = "received_at",
		order: str = "desc",
		limit: int = Query(default=50, ge=1, le=100),
		offset: int = Query(default=0, ge=0),
	) -> dict[str, Any]:
		filters = {
			"q": q,
			"account_id": account_id,
			"read_status": read_status,
			"has_attachment": has_attachment,
			"summary_status": summary_status,
			"date_from": date_from,
			"date_to": date_to,
			"sort": sort,
			"order": order,
			"limit": limit,
			"offset": offset,
		}
		data = email_platform.store.search_messages(filters)
		total = email_platform.store.count_messages(filters)
		return {"data": data, "total": total, "limit": limit, "offset": offset}

	@router.get("/email/messages/{message_id}")
	async def get_message_detail(message_id: str) -> dict[str, Any]:
		row = email_platform.store.get_message_detail(message_id)
		if not row:
			raise HTTPException(status_code=404, detail="message not found")
		return row

	@router.get("/email/messages/{message_id}/raw")
	async def get_message_raw(message_id: str):
		message = email_platform.store.get_message(message_id)
		if not message:
			raise HTTPException(status_code=404, detail="message not found")
		eml_path = str(message.get("eml_path") or "")
		if eml_path:
			return FileResponse(eml_path, media_type="message/rfc822", filename=f"{message_id}.eml")
		raise HTTPException(status_code=404, detail="eml not stored")

	@router.get("/email/attachments/{attachment_id}")
	async def get_attachment(attachment_id: int):
		row = email_platform.store.get_attachment(attachment_id)
		if not row:
			raise HTTPException(status_code=404, detail="attachment not found")
		path = str(row["storage_uri"])
		return FileResponse(path, media_type=str(row["mime_type"]), filename=str(row["filename"]))

	return router
