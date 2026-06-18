from __future__ import annotations

import base64
import re
from email import policy
from email.parser import BytesParser
from typing import Any


def _b64url_decode(data: str) -> bytes:
	padded = data + "=" * (-len(data) % 4)
	return base64.urlsafe_b64decode(padded.encode("ascii"))


def extract_headers(payload: dict[str, Any]) -> dict[str, str]:
	headers: dict[str, str] = {}
	for item in payload.get("headers") or []:
		if not isinstance(item, dict):
			continue
		name = str(item.get("name") or "").strip()
		value = str(item.get("value") or "").strip()
		if name:
			headers[name] = value
	return headers


def _walk_parts(part: dict[str, Any], texts: list[str], attachments: list[dict[str, Any]]) -> None:
	mime = str(part.get("mimeType") or "")
	body = part.get("body") or {}
	filename = str(part.get("filename") or "")
	if filename and body.get("attachmentId"):
		attachments.append(
			{
				"filename": filename,
				"mime_type": mime or "application/octet-stream",
				"attachment_id": str(body["attachmentId"]),
				"size_bytes": int(body.get("size") or 0),
			}
		)
	elif mime == "text/plain" and body.get("data"):
		try:
			texts.append(_b64url_decode(str(body["data"])).decode("utf-8", errors="replace"))
		except Exception:
			pass
	for child in part.get("parts") or []:
		if isinstance(child, dict):
			_walk_parts(child, texts, attachments)


def parse_gmail_message(message: dict[str, Any]) -> dict[str, Any]:
	payload = message.get("payload") or {}
	headers = extract_headers(payload)
	texts: list[str] = []
	attachments: list[dict[str, Any]] = []
	if payload:
		_walk_parts(payload, texts, attachments)
	body_text = "\n".join(texts).strip()
	if not body_text and message.get("snippet"):
		body_text = str(message["snippet"])
	from_address = headers.get("From", "")
	to_raw = headers.get("To", "")
	to_addresses = [part.strip() for part in to_raw.split(",") if part.strip()]
	subject = headers.get("Subject", "")
	received_at = str(message.get("internalDate") or "")
	thread_id = str(message.get("threadId") or "")
	message_id = str(message.get("id") or "")
	return {
		"message_id": message_id,
		"thread_id": thread_id,
		"subject": subject,
		"body_text": body_text,
		"from_address": from_address,
		"to_addresses": to_addresses,
		"headers": headers,
		"participants": _unique_addresses(from_address, to_addresses),
		"received_at": received_at,
		"attachments": attachments,
		"history_id": str(message.get("historyId") or ""),
	}


def parse_raw_eml(raw_bytes: bytes) -> dict[str, Any]:
	msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)
	subject = str(msg.get("Subject") or "")
	from_address = str(msg.get("From") or "")
	to_addresses = [part.strip() for part in str(msg.get("To") or "").split(",") if part.strip()]
	body_text = ""
	if msg.is_multipart():
		for part in msg.walk():
			if part.get_content_type() == "text/plain" and not part.get_filename():
				body_text = str(part.get_content() or "")
				break
	else:
		body_text = str(msg.get_content() or "")
	headers = {key: str(value) for key, value in msg.items()}
	return {
		"subject": subject,
		"body_text": body_text.strip(),
		"from_address": from_address,
		"to_addresses": to_addresses,
		"headers": headers,
		"participants": _unique_addresses(from_address, to_addresses),
	}


def _unique_addresses(from_address: str, to_addresses: list[str]) -> list[str]:
	seen: set[str] = set()
	out: list[str] = []
	for raw in [from_address, *to_addresses]:
		match = re.search(r"<([^>]+)>", raw)
		addr = (match.group(1) if match else raw).strip().lower()
		if addr and addr not in seen:
			seen.add(addr)
			out.append(addr)
	return out
