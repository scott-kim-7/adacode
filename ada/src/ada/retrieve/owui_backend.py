from __future__ import annotations

import logging
from typing import Any

import httpx

from ada.agent.jwt_context import jwt_authorization_header
from ada.ports import owui_base_url

log = logging.getLogger(__name__)


class OwuiRetrievalBackend:
	def __init__(self, base_url: str | None = None, *, timeout_s: float = 120.0) -> None:
		self._base_url = (base_url or owui_base_url()).rstrip("/")
		self._timeout = timeout_s

	async def fetch_sources(
		self,
		items: list[dict[str, Any]],
		queries: list[str],
		*,
		full_context: bool = False,
		jwt: bytearray | None,
	) -> list[dict[str, Any]]:
		if not jwt or not queries:
			return []
		url = f"{self._base_url}/api/v1/ada/retrieval/sources"
		payload = {"items": items, "queries": queries, "full_context": full_context}
		headers = jwt_authorization_header(jwt)
		try:
			async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, connect=10.0)) as client:
				resp = await client.post(url, json=payload, headers=headers)
				resp.raise_for_status()
				data = resp.json()
		except httpx.HTTPError as exc:
			log.warning("OwuiRetrievalBackend fetch_sources failed: %s", exc)
			return []
		if isinstance(data, dict) and isinstance(data.get("sources"), list):
			return data["sources"]
		return []
