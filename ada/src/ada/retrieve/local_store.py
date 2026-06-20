from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_DEFAULT_INDEX = Path(__file__).resolve().parents[3] / ".local" / "agent_retrieval" / "index.json"


def retrieval_index_path() -> Path:
	import os

	raw = os.environ.get("ADA_AGENT_RETRIEVAL_INDEX", "").strip()
	return Path(raw) if raw else _DEFAULT_INDEX


def load_index(path: Path | None = None) -> list[dict[str, Any]]:
	store = path or retrieval_index_path()
	if not store.is_file():
		return []
	try:
		data = json.loads(store.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError):
		return []
	return data if isinstance(data, list) else []


def save_index(entries: list[dict[str, Any]], path: Path | None = None) -> None:
	store = path or retrieval_index_path()
	store.parent.mkdir(parents=True, exist_ok=True)
	store.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _tokenize(text: str) -> set[str]:
	return {token for token in re.findall(r"[a-zA-Z0-9가-힣_]+", text.lower()) if token}


def search_local_index(queries: list[str], *, k: int = 5, path: Path | None = None) -> list[dict[str, Any]]:
	query_text = " ".join(str(q) for q in queries if str(q).strip()).strip()
	if not query_text:
		return []
	query_tokens = _tokenize(query_text)
	if not query_tokens:
		return []

	scored: list[tuple[int, dict[str, Any]]] = []
	for entry in load_index(path):
		if not isinstance(entry, dict):
			continue
		text = str(entry.get("text") or "")
		tokens = _tokenize(text)
		if not tokens:
			continue
		score = len(query_tokens & tokens)
		if score > 0:
			scored.append((score, entry))

	scored.sort(key=lambda item: item[0], reverse=True)
	sources: list[dict[str, Any]] = []
	for _, entry in scored[:k]:
		sources.append(
			{
				"document": [str(entry.get("text") or "")],
				"metadata": [entry.get("metadata") or {}],
				"source": entry.get("source") or {"type": "local"},
			}
		)
	return sources
