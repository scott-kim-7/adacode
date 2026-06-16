from __future__ import annotations

import json
from typing import Any

REASONING_KEYS = frozenset({"reasoning", "reasoning_content", "thinking"})


def clean_stream_delta(delta: dict[str, Any], *, include_role: bool) -> dict[str, Any]:
	clean: dict[str, Any] = {}
	if include_role and delta.get("role"):
		clean["role"] = delta["role"]
	content = delta.get("content")
	if content is not None and content != "":
		clean["content"] = content
	for key, value in delta.items():
		if key in REASONING_KEYS or value is None:
			continue
		if key in {"role", "content"}:
			continue
		clean[key] = value
	return clean


def strip_reasoning_from_chunk(data: dict[str, Any]) -> dict[str, Any]:
	for choice in data.get("choices") or []:
		if not isinstance(choice, dict):
			continue
		delta = choice.get("delta")
		if isinstance(delta, dict):
			include_role = bool(delta.get("role")) and not delta.get("content")
			choice["delta"] = clean_stream_delta(delta, include_role=include_role)
		message = choice.get("message")
		if isinstance(message, dict):
			for key in REASONING_KEYS:
				message.pop(key, None)
	return data


def is_sse_done_line(line: str) -> bool:
	stripped = line.strip()
	return stripped == "data: [DONE]" or stripped.endswith("[DONE]")


def parse_sse_data_line(line: str) -> dict[str, Any] | None:
	stripped = line.strip()
	if not stripped.startswith("data:"):
		return None
	payload = stripped[5:].strip()
	if not payload or payload == "[DONE]":
		return None
	try:
		data = json.loads(payload)
	except json.JSONDecodeError:
		return None
	if not isinstance(data, dict):
		return None
	return strip_reasoning_from_chunk(data)


def content_delta_from_chunk(data: dict[str, Any]) -> str | None:
	for choice in data.get("choices") or []:
		if not isinstance(choice, dict):
			continue
		delta = choice.get("delta")
		if isinstance(delta, dict):
			content = delta.get("content")
			if content is not None and content != "":
				return str(content)
	return None


def finish_reason_from_chunk(data: dict[str, Any]) -> str | None:
	for choice in data.get("choices") or []:
		if not isinstance(choice, dict):
			continue
		reason = choice.get("finish_reason")
		if reason:
			return str(reason)
	return None
