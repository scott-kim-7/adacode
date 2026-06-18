from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class GmailSendResult:
	provider_message_id: str
	status: str


class GmailSender:
	"""Local stub for Gmail send — does not call the Gmail API.

	Replace with a real Gmail API client in Phase 1+ while keeping this interface.
	"""

	def send_reply(self, *, thread_id: str, to_address: str, subject: str, body: str) -> GmailSendResult:
		token = f"{thread_id}:{to_address}:{subject}:{len(body)}"
		digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
		return GmailSendResult(provider_message_id=f"local-{digest}", status="sent")
