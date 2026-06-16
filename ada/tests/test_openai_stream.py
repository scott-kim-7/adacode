from __future__ import annotations

from ada.openai_stream import (
	clean_stream_delta,
	content_delta_from_chunk,
	is_sse_done_line,
	parse_sse_data_line,
	strip_reasoning_from_chunk,
)


def test_clean_stream_delta_strips_reasoning_null():
	delta = {"role": "assistant", "content": "hi", "reasoning": None}
	clean = clean_stream_delta(delta, include_role=True)
	assert clean == {"role": "assistant", "content": "hi"}


def test_parse_sse_data_line_extracts_content():
	line = 'data: {"choices":[{"delta":{"content":"안"}}]}'
	data = parse_sse_data_line(line)
	assert data is not None
	assert content_delta_from_chunk(data) == "안"


def test_strip_reasoning_from_chunk():
	raw = {
		"choices": [
			{"delta": {"role": "assistant", "content": None, "reasoning": None}},
		]
	}
	cleaned = strip_reasoning_from_chunk(raw)
	delta = cleaned["choices"][0]["delta"]
	assert "reasoning" not in delta
	assert delta.get("role") == "assistant"


def test_is_sse_done_line():
	assert is_sse_done_line("data: [DONE]")
	assert is_sse_done_line("  data: [DONE]  ")
	assert not is_sse_done_line('data: {"choices":[]}')
