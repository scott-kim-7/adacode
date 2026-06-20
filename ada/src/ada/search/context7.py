from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CONTEXT7_API_BASE = "https://context7.com/api/v2"


def _fixture_path(name: str) -> Path:
	return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / name


def parse_libs_search_response(data: dict[str, Any]) -> list[dict[str, str]]:
	items = data.get("results") or data.get("libraries") or data.get("data") or []
	out: list[dict[str, str]] = []
	if not isinstance(items, list):
		return out
	for item in items:
		if not isinstance(item, dict):
			continue
		lib_id = str(item.get("libraryId") or item.get("id") or item.get("library_id") or "")
		name = str(item.get("name") or item.get("libraryName") or item.get("title") or "")
		if lib_id or name:
			out.append({"libraryId": lib_id, "name": name})
	return out


def parse_context_response(data: dict[str, Any]) -> str:
	for key in ("context", "content", "text", "data"):
		value = data.get(key)
		if isinstance(value, str) and value.strip():
			return value
		if isinstance(value, dict):
			nested = value.get("content") or value.get("text")
			if isinstance(nested, str) and nested.strip():
				return nested
	return json.dumps(data, ensure_ascii=False)[:8000]


def search_library(api_key: str, library_name: str, query: str) -> list[dict[str, str]]:
	url = f"{CONTEXT7_API_BASE}/libs/search"
	params = {"libraryName": library_name, "query": query}
	headers = {"Authorization": f"Bearer {api_key}"}
	try:
		with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
			resp = client.get(url, params=params, headers=headers)
			resp.raise_for_status()
			data = resp.json()
	except httpx.HTTPError as exc:
		log.warning("Context7 libs/search failed: %s", exc)
		fixture = _fixture_path("context7_libs_search.json")
		if fixture.is_file():
			data = json.loads(fixture.read_text())
		else:
			return []
	if not isinstance(data, dict):
		return []
	return parse_libs_search_response(data)


def fetch_context(api_key: str, library_id: str, query: str) -> str:
	url = f"{CONTEXT7_API_BASE}/context"
	params = {"libraryId": library_id, "query": query, "type": "json"}
	headers = {"Authorization": f"Bearer {api_key}"}
	try:
		with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
			resp = client.get(url, params=params, headers=headers)
			resp.raise_for_status()
			data = resp.json()
	except httpx.HTTPError as exc:
		log.warning("Context7 context failed: %s", exc)
		return ""
	if not isinstance(data, dict):
		return ""
	return parse_context_response(data)
