from __future__ import annotations

import logging
from typing import Any

from ada.owui_adapt.exa import SearchResult, search_exa
from ada.search.context7 import fetch_context, search_library
from ada.search.heuristics import select_search_providers
from ada.vault import VaultError, VaultSession
from ada.vault_secrets import resolve_vault_secret

log = logging.getLogger(__name__)

EXA_VAULT_KEY = "exa.api_key"
CONTEXT7_VAULT_KEY = "context7.api_key"


def _vault_key(session: VaultSession | None, key: str) -> str | None:
	try:
		return resolve_vault_secret(key, session)
	except VaultError:
		return None


def run_search_batch(
	query: str,
	*,
	vault_session: VaultSession | None = None,
	max_results: int = 5,
) -> list[dict[str, Any]]:
	text = (query or "").strip()
	if not text:
		return []

	providers = select_search_providers(text)
	docs: list[str] = []
	urls: list[str] = []

	for provider in providers:
		if provider == "exa":
			exa_key = _vault_key(vault_session, EXA_VAULT_KEY)
			if exa_key:
				for result in search_exa(exa_key, text, max_results):
					docs.append(_format_exa_doc(result))
					urls.append(result.link)
		if provider == "context7":
			c7_key = _vault_key(vault_session, CONTEXT7_VAULT_KEY)
			if c7_key:
				libs = search_library(c7_key, text, text)
				if libs:
					lib_id = libs[0].get("libraryId") or libs[0].get("name") or ""
					if lib_id:
						ctx = fetch_context(c7_key, lib_id, text)
						if ctx:
							docs.append(ctx)
							urls.append(f"context7://{lib_id}")

	if not docs:
		return []

	return [
		{
			"docs": docs,
			"name": text,
			"type": "web_search",
			"urls": urls,
			"queries": [text],
		}
	]


def _format_exa_doc(result: SearchResult) -> str:
	title = result.title.strip()
	body = result.snippet.strip()
	if title and body:
		return f"{title}\n{body}"
	return title or body or result.link
