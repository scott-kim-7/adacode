from __future__ import annotations

from ada.retrieve.local_store import save_index, search_local_index


def test_search_local_index_keyword(tmp_path):
	index = tmp_path / "index.json"
	save_index(
		[
			{"text": "FastAPI routing guide", "metadata": {}, "source": {}},
			{"text": "Unrelated cooking recipe", "metadata": {}, "source": {}},
		],
		index,
	)
	hits = search_local_index(["fastapi routing"], path=index)
	assert len(hits) == 1
	assert "FastAPI" in hits[0]["document"][0]
