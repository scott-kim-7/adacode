from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ada.retrieve.owui_backend import OwuiRetrievalBackend


def test_retrieval_backend_sends_jwt_and_queries():
	backend = OwuiRetrievalBackend(base_url="http://example.test")
	jwt = bytearray(b"Bearer user-jwt")
	mock_resp = MagicMock()
	mock_resp.raise_for_status = MagicMock()
	mock_resp.json = MagicMock(
		return_value={"sources": [{"document": ["doc"], "metadata": [{}], "source": {"id": "1"}}]}
	)
	captured: dict = {}

	async def _post(url, json=None, headers=None):
		captured["url"] = url
		captured["json"] = json
		captured["headers"] = headers
		return mock_resp

	mock_client = AsyncMock()
	mock_client.post = _post
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=None)

	with patch("httpx.AsyncClient", return_value=mock_client):
		sources = asyncio.run(backend.fetch_sources([], ["query text"], jwt=jwt))
	assert sources
	assert captured["headers"]["Authorization"] == "Bearer user-jwt"
	assert captured["json"]["queries"] == ["query text"]
