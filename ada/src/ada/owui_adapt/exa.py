from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

EXA_API_BASE = "https://api.exa.ai"


@dataclass(frozen=True)
class SearchResult:
	link: str
	title: str
	snippet: str


def search_exa(
	api_key: str,
	query: str,
	count: int,
	filter_list: list[str] | None = None,
) -> list[SearchResult]:
	headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
	payload: dict[str, Any] = {
		"query": query,
		"numResults": count or 5,
		"includeDomains": filter_list,
		"contents": {"text": True, "highlights": True},
		"type": "auto",
	}
	try:
		with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
			resp = client.post(f"{EXA_API_BASE}/search", headers=headers, json=payload)
			resp.raise_for_status()
			data = resp.json()
	except httpx.HTTPError as exc:
		log.warning("Exa search failed: %s", exc)
		return []

	results: list[SearchResult] = []
	for item in data.get("results") or []:
		if not isinstance(item, dict):
			continue
		results.append(
			SearchResult(
				link=str(item.get("url") or ""),
				title=str(item.get("title") or ""),
				snippet=str(item.get("text") or ""),
			)
		)
	return results
