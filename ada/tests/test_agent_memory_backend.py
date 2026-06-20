from __future__ import annotations

import asyncio
from unittest.mock import patch

from ada.memory.agent_backend import AgentMemoryBackend
from ada.memory.factory import save_memories


def test_agent_memory_backend_keyword_query(tmp_path):
	store = tmp_path / "memories.json"
	save_memories(
		[
			{"content": "User prefers dark mode", "created_at": 1700000000},
			{"content": "Favorite language is Python", "created_at": 1700000100},
		],
		store,
	)
	backend = AgentMemoryBackend()
	with patch("ada.memory.agent_backend.load_memories", lambda: __import__("json").loads(store.read_text())):
		result = asyncio.run(backend.query("python programming", 2, None))
	assert any("Python" in doc for doc in result.documents)
