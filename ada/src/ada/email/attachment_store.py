from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ada.email.paths import email_attachments_dir, email_raw_dir


@dataclass(frozen=True)
class SavedAttachment:
	filename: str
	mime_type: str
	size_bytes: int
	storage_uri: str
	sha256: str


class AttachmentStore:
	def save_eml(self, *, account_id: str, message_id: str, raw_bytes: bytes) -> str:
		target = email_raw_dir(account_id) / f"{message_id}.eml"
		target.parent.mkdir(parents=True, exist_ok=True)
		target.write_bytes(raw_bytes)
		return str(target)

	def save_attachment(
		self,
		*,
		account_id: str,
		message_id: str,
		filename: str,
		mime_type: str,
		data: bytes,
		max_bytes: int | None,
	) -> SavedAttachment | None:
		if max_bytes is not None and len(data) > max_bytes:
			return None
		target_dir = email_attachments_dir(account_id, message_id)
		target_dir.mkdir(parents=True, exist_ok=True)
		safe_name = Path(filename).name or "attachment.bin"
		target = target_dir / safe_name
		target.write_bytes(data)
		digest = hashlib.sha256(data).hexdigest()
		return SavedAttachment(
			filename=safe_name,
			mime_type=mime_type,
			size_bytes=len(data),
			storage_uri=str(target),
			sha256=digest,
		)

	def read_file(self, storage_uri: str) -> bytes:
		path = Path(storage_uri)
		if not path.is_file():
			raise FileNotFoundError(storage_uri)
		return path.read_bytes()
