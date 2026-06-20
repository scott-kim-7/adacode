from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ada.memory.owui_backend import MemoryResult, OwuiMemoryBackend, format_memory_context


def test_memory_backend_formats_context():
	result = MemoryResult(documents=["hello"], dates=["2026-01-01"])
	text = format_memory_context(result)
	assert "User Context:" in text
	assert "[2026-01-01] hello" in text


def test_memory_backend_404_returns_empty():
	backend = OwuiMemoryBackend(base_url="http://example.test")
	jwt = bytearray(b"Bearer test")
	mock_resp = MagicMock()
	mock_resp.status_code = 404
	mock_client = AsyncMock()
	mock_client.post = AsyncMock(return_value=mock_resp)
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=None)
	with patch("httpx.AsyncClient", return_value=mock_client):
		result = asyncio.run(backend.query("hello", 3, jwt))
	assert result.documents == []
