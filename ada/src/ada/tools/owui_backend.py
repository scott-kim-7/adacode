from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ada.agent.jwt_context import jwt_authorization_header
from ada.ports import owui_base_url

log = logging.getLogger(__name__)


class OwuiToolBackend:
	def __init__(self, base_url: str | None = None) -> None:
		self._base_url = (base_url or owui_base_url()).rstrip("/")

	async def execute(
		self,
		name: str,
		arguments: str,
		tool_ids: list[str],
		jwt: bytearray | None,
	) -> str:
		if not tool_ids:
			return json.dumps({"error": "tool_ids missing in metadata"})
		try:
			args = json.loads(arguments or "{}")
		except json.JSONDecodeError:
			args = {}
		if not isinstance(args, dict):
			args = {}

		url = f"{self._base_url}/api/v1/ada/tools/execute"
		headers = {"Content-Type": "application/json", **jwt_authorization_header(jwt)}
		payload: dict[str, Any] = {
			"name": name,
			"arguments": args,
			"tool_ids": tool_ids,
		}
		try:
			async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
				response = await client.post(url, json=payload, headers=headers)
				response.raise_for_status()
				data = response.json()
		except Exception as exc:
			log.warning("OwuiToolBackend execute failed for %s: %s", name, exc)
			return json.dumps({"error": str(exc)})

		content = data.get("content")
		if content is None:
			return json.dumps(data)
		return str(content)
