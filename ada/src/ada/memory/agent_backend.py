from __future__ import annotations

import time

from ada.memory.factory import load_memories
from ada.memory.owui_backend import MemoryResult


class AgentMemoryBackend:
	"""Local keyword memory store (Phase 6). Replaces OWUI vector HTTP when enabled."""

	async def query(self, content: str, k: int, jwt: bytearray | None) -> MemoryResult:
		del jwt
		query = (content or "").strip().lower()
		if not query:
			return MemoryResult(documents=[], dates=[])

		scored: list[tuple[int, dict]] = []
		for entry in load_memories():
			if not isinstance(entry, dict):
				continue
			text = str(entry.get("content") or "")
			needle = text.lower()
			if not needle:
				continue
			score = 0
			for token in query.split():
				if token and token in needle:
					score += 1
			if score > 0:
				scored.append((score, entry))

		scored.sort(key=lambda item: item[0], reverse=True)
		documents: list[str] = []
		dates: list[str] = []
		for _, entry in scored[: max(k, 1)]:
			documents.append(str(entry.get("content") or ""))
			created = entry.get("created_at")
			if created:
				dates.append(time.strftime("%Y-%m-%d", time.localtime(int(created))))
			else:
				dates.append("Unknown Date")
		return MemoryResult(documents=documents, dates=dates)
