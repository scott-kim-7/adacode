from __future__ import annotations

import logging
import os
from typing import Any

from ada.retrieve.local_store import search_local_index
from ada.retrieve.owui_backend import OwuiRetrievalBackend

log = logging.getLogger(__name__)

_VECTOR_ITEM_TYPES = frozenset(
	{"file", "collection", "note", "chat", "url", "collection_name"},
)


def _sources_from_web_search_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	sources: list[dict[str, Any]] = []
	for item in items:
		if not isinstance(item, dict):
			continue
		if item.get("type") != "web_search":
			continue
		docs = item.get("docs")
		if not isinstance(docs, list):
			continue
		for doc in docs:
			if isinstance(doc, dict):
				content = doc.get("content") or doc.get("snippet") or doc.get("title") or ""
			else:
				content = str(doc)
			if not str(content).strip():
				continue
			sources.append(
				{
					"document": [str(content)],
					"metadata": [{"source": item.get("name") or "web_search"}],
					"source": {"type": "web_search", "name": item.get("name")},
				}
			)
	return sources


def _sources_from_inline_docs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	sources: list[dict[str, Any]] = []
	for item in items:
		if not isinstance(item, dict):
			continue
		if item.get("type") == "web_search":
			continue
		docs = item.get("docs")
		if not isinstance(docs, list):
			continue
		for doc in docs:
			text = doc if isinstance(doc, str) else str(doc.get("content") or doc)
			if text.strip():
				sources.append(
					{
						"document": [text],
						"metadata": [{}],
						"source": {"type": item.get("type") or "docs"},
					}
				)
	return sources


class AgentRetrievalBackend:
	"""Phase 6 retrieval: inline web_search/docs without OWUI HTTP; optional OWUI fallback."""

	def __init__(self, *, owui_fallback: bool | None = None) -> None:
		if owui_fallback is None:
			owui_fallback = os.environ.get("ADA_AGENT_RETRIEVAL_FALLBACK_OWUI", "1").strip().lower() in (
				"1",
				"true",
				"yes",
			)
		self._owui_fallback = owui_fallback
		self._owui = OwuiRetrievalBackend()

	async def fetch_sources(
		self,
		items: list[dict[str, Any]],
		queries: list[str],
		*,
		full_context: bool = False,
		jwt: bytearray | None,
	) -> list[dict[str, Any]]:
		inline = _sources_from_web_search_items(items) + _sources_from_inline_docs(items)
		needs_vector = any(
			isinstance(item, dict) and item.get("type") in _VECTOR_ITEM_TYPES for item in items
		)
		if needs_vector:
			local = search_local_index(queries)
			if local:
				return inline + local
			if self._owui_fallback and jwt:
				log.debug("AgentRetrievalBackend delegating vector items to OWUI adapter")
				remote = await self._owui.fetch_sources(
					items,
					queries,
					full_context=full_context,
					jwt=jwt,
				)
				return inline + remote
		return inline
