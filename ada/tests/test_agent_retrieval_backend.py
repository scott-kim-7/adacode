from __future__ import annotations

import asyncio
from unittest.mock import patch

from ada.retrieve.agent_backend import AgentRetrievalBackend
from ada.retrieve.local_store import save_index, search_local_index


def test_agent_retrieval_web_search_docs_inline():
	backend = AgentRetrievalBackend(owui_fallback=False)
	items = [
		{
			"type": "web_search",
			"name": "exa",
			"docs": [{"content": "Result A"}, {"content": "Result B"}],
		}
	]
	sources = asyncio.run(backend.fetch_sources(items, ["query"], jwt=None))
	assert len(sources) == 2
	assert sources[0]["document"] == ["Result A"]


def test_agent_retrieval_local_index_for_vector_items(tmp_path):
	index = tmp_path / "index.json"
	save_index(
		[
			{
				"text": "Python asyncio tutorial for beginners",
				"metadata": {"collection": "docs"},
				"source": {"type": "collection"},
			}
		],
		index,
	)
	backend = AgentRetrievalBackend(owui_fallback=False)
	with patch(
		"ada.retrieve.agent_backend.search_local_index",
		lambda queries, k=5, path=None: search_local_index(queries, k=k, path=index),
	):
		sources = asyncio.run(
			backend.fetch_sources(
				[{"type": "collection", "id": "c1"}],
				["asyncio python"],
				jwt=None,
			)
		)
	assert sources
	assert "asyncio" in sources[0]["document"][0].lower()
