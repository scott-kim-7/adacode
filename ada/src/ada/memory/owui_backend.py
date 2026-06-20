from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from ada.agent.jwt_context import jwt_authorization_header
from ada.ports import owui_base_url

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryResult:
	documents: list[str]
	dates: list[str]


class OwuiMemoryBackend:
	def __init__(self, base_url: str | None = None, *, timeout_s: float = 30.0) -> None:
		self._base_url = (base_url or owui_base_url()).rstrip("/")
		self._timeout = timeout_s

	async def query(self, content: str, k: int, jwt: bytearray | None) -> MemoryResult:
		if not jwt:
			return MemoryResult(documents=[], dates=[])
		url = f"{self._base_url}/api/v1/memories/query"
		payload = {"content": content, "k": k}
		headers = jwt_authorization_header(jwt)
		try:
			async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, connect=5.0)) as client:
				resp = await client.post(url, json=payload, headers=headers)
				if resp.status_code == 404:
					return MemoryResult(documents=[], dates=[])
				resp.raise_for_status()
				data = resp.json()
		except httpx.HTTPError as exc:
			log.warning("OwuiMemoryBackend query failed: %s", exc)
			return MemoryResult(documents=[], dates=[])

		documents: list[str] = []
		dates: list[str] = []
		if isinstance(data, dict):
			docs = data.get("documents")
			metas = data.get("metadatas")
			if isinstance(docs, list) and docs and isinstance(docs[0], list):
				row_docs = docs[0]
				row_meta = metas[0] if isinstance(metas, list) and metas and isinstance(metas[0], list) else []
				for idx, doc in enumerate(row_docs):
					documents.append(str(doc))
					created = ""
					if idx < len(row_meta) and isinstance(row_meta[idx], dict):
						ts = row_meta[idx].get("created_at")
						if ts:
							created = time.strftime("%Y-%m-%d", time.localtime(int(ts)))
					dates.append(created or "Unknown Date")
		return MemoryResult(documents=documents, dates=dates)


def format_memory_context(result: MemoryResult) -> str:
	if not result.documents:
		return ""
	lines = ["User Context:"]
	for idx, doc in enumerate(result.documents):
		date = result.dates[idx] if idx < len(result.dates) else "Unknown Date"
		lines.append(f"{idx + 1}. [{date}] {doc}")
	return "\n".join(lines) + "\n"
