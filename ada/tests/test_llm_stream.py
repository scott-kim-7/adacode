from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from ada.llm import ChatMessage, LLMClient
from ada.registry import Profile


class _HangingLineIterator:
	def __init__(self, lines: list[str]) -> None:
		self._lines = iter(lines)

	def __iter__(self) -> Iterator[str]:
		return self

	def __next__(self) -> str:
		try:
			return next(self._lines)
		except StopIteration:
			raise TimeoutError("iter_lines should have stopped before hanging") from None


def test_chat_completion_stream_stops_on_finish_reason():
	profile = Profile(
		name="test",
		label="test",
		provider="openai",
		base_url="http://127.0.0.1:8080/v1",
		api_key="local",
	)
	client = LLMClient(profile, api_key="local")
	deltas: list[str] = []

	lines = [
		'data: {"choices":[{"delta":{"content":"안"}}]}',
		'data: {"choices":[{"index":0,"finish_reason":"stop","delta":{}}]}',
		"data: [DONE]",
	]
	mock_resp = MagicMock()
	mock_resp.iter_lines.return_value = _HangingLineIterator(lines)
	mock_resp.raise_for_status = MagicMock()

	mock_stream_ctx = MagicMock()
	mock_stream_ctx.__enter__.return_value = mock_resp

	with (
		patch.object(client, "_model", return_value="test-model"),
		patch.object(client._client, "stream", return_value=mock_stream_ctx),
	):
		result = client.chat_completion_stream(
			[ChatMessage(role="user", content="안녕")],
			on_delta=deltas.append,
		)

	assert deltas == ["안"]
	assert result.content == "안"
	assert result.finish_reason == "stop"
