from __future__ import annotations

import os
from pathlib import Path


def email_data_root() -> Path:
	override = os.environ.get("ADA_EMAIL_DATA_ROOT", "").strip()
	if override:
		return Path(override)
	return Path(__file__).resolve().parents[3] / "data"


def email_raw_dir(account_id: str) -> Path:
	return email_data_root() / "email_raw" / account_id


def email_attachments_dir(account_id: str, message_id: str) -> Path:
	return email_data_root() / "email_attachments" / account_id / message_id
