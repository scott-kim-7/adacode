from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

RequestKind = Literal["chat", "task", "tool"]

PHASE2_METADATA_ALLOWLIST = frozenset(
	{
		"features",
		"files",
		"chat_id",
		"message_id",
		"tool_ids",
		"tool_servers",
		"collection_names",
		"task",
		"task_body",
		"filter_ids",
	}
)


def parse_request_metadata(
	headers: Mapping[str, str],
	payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
	raw = headers.get("x-openwebui-metadata") or headers.get("X-OpenWebUI-Metadata")
	meta: dict[str, Any] = {}
	if raw:
		try:
			parsed = json.loads(raw)
			if isinstance(parsed, dict):
				meta = parsed
		except json.JSONDecodeError:
			meta = {}
	if not meta and payload:
		candidate = payload.get("metadata")
		if isinstance(candidate, dict):
			meta = candidate
	return meta


def classify_request(
	headers: Mapping[str, str],
	payload: dict[str, Any],
) -> RequestKind:
	kind = (headers.get("x-ada-request-kind") or headers.get("X-Ada-Request-Kind") or "").strip().lower()
	if kind in ("chat", "task", "tool"):
		return kind  # type: ignore[return-value]

	meta = parse_request_metadata(headers, payload)
	if meta.get("task"):
		return "task"

	tools = payload.get("tools")
	if isinstance(tools, list) and tools:
		return "tool"
	return "chat"


def filter_metadata_for_header(metadata: dict[str, Any]) -> dict[str, Any]:
	return {key: metadata[key] for key in PHASE2_METADATA_ALLOWLIST if key in metadata}
