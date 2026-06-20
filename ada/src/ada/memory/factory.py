from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Protocol

from ada.memory.owui_backend import MemoryResult

log = logging.getLogger(__name__)

_DEFAULT_STORE = Path(__file__).resolve().parents[3] / ".local" / "agent_memory" / "memories.json"


class MemoryBackend(Protocol):
	async def query(self, content: str, k: int, jwt: bytearray | None) -> MemoryResult: ...


def agent_memory_store_path() -> Path:
	raw = os.environ.get("ADA_AGENT_MEMORY_STORE", "").strip()
	return Path(raw) if raw else _DEFAULT_STORE


def use_agent_backends() -> bool:
	return os.environ.get("ADA_USE_AGENT_BACKENDS", "").strip().lower() in (
		"1",
		"true",
		"yes",
	)


def get_memory_backend():
	if use_agent_backends():
		from ada.memory.agent_backend import AgentMemoryBackend

		return AgentMemoryBackend()
	from ada.memory.owui_backend import OwuiMemoryBackend

	return OwuiMemoryBackend()


def load_memories(path: Path | None = None) -> list[dict]:
	store = path or agent_memory_store_path()
	if not store.is_file():
		return []
	try:
		data = json.loads(store.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError):
		return []
	return data if isinstance(data, list) else []


def save_memories(memories: list[dict], path: Path | None = None) -> None:
	store = path or agent_memory_store_path()
	store.parent.mkdir(parents=True, exist_ok=True)
	store.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding="utf-8")
