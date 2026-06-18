from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_ADA_ALIASES: tuple[str, ...] = ("ada", "아다")

REPLY_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = (
	re.compile(r"\b(reply|respond|response|please\s+reply|please\s+respond)\b", re.IGNORECASE),
	re.compile(r"\b(답장|회신|응답|답변|의견\s*줘|의견\s*부탁)\b"),
	re.compile(r"\b(답\s*줘|답변\s*줘|회신\s*부탁|reply\s+to\s+this)\b", re.IGNORECASE),
)

AUTO_REPLY_HEADER_VALUES: tuple[str, ...] = (
	"auto-generated",
	"auto-replied",
	"auto-notified",
)


@dataclass(frozen=True)
class TriggerDecision:
	detected_mention: bool
	detected_reply_intent: bool
	allowed_to_reply: bool
	reason: str


def _normalize(text: str) -> str:
	return " ".join(text.strip().split())


def detect_ada_mention(text: str, aliases: tuple[str, ...] = DEFAULT_ADA_ALIASES) -> bool:
	normalized = _normalize(text).lower()
	if not normalized:
		return False
	for alias in aliases:
		token = alias.strip().lower()
		if not token:
			continue
		if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", normalized):
			return True
	return False


def detect_reply_intent(text: str) -> bool:
	normalized = _normalize(text)
	if not normalized:
		return False
	return any(pattern.search(normalized) for pattern in REPLY_REQUEST_PATTERNS)


def _is_noreply_address(sender: str) -> bool:
	value = sender.lower()
	return any(keyword in value for keyword in ("no-reply", "noreply", "do-not-reply", "donotreply"))


def is_noreply_address(sender: str) -> bool:
	return _is_noreply_address(sender)


def evaluate_reply_policy(
	*,
	subject: str,
	body: str,
	sender: str,
	headers: dict[str, str] | None = None,
	aliases: tuple[str, ...] = DEFAULT_ADA_ALIASES,
	allowed_domains: tuple[str, ...] | None = None,
) -> TriggerDecision:
	headers = headers or {}
	content = f"{subject}\n{body}".strip()
	detected_mention = detect_ada_mention(content, aliases)
	detected_reply_intent = detect_reply_intent(content)

	if not detected_mention:
		return TriggerDecision(False, detected_reply_intent, False, "ada_not_mentioned")
	if not detected_reply_intent:
		return TriggerDecision(True, False, False, "reply_intent_missing")
	if _is_noreply_address(sender):
		return TriggerDecision(True, True, False, "noreply_sender")

	auto_submitted = headers.get("Auto-Submitted", "").strip().lower()
	if auto_submitted in AUTO_REPLY_HEADER_VALUES:
		return TriggerDecision(True, True, False, "auto_submitted_message")
	if headers.get("List-Id"):
		return TriggerDecision(True, True, False, "mailing_list_message")

	if allowed_domains:
		sender_domain = sender.rsplit("@", 1)[-1].lower() if "@" in sender else ""
		if sender_domain not in {d.lower() for d in allowed_domains}:
			return TriggerDecision(True, True, False, "sender_domain_blocked")

	return TriggerDecision(True, True, True, "policy_passed")
