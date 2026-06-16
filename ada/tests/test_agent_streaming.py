from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from ada.agent.config import (
	AgentConfig,
	PlanConfig,
	RespondConfig,
	RoutingConfig,
	StreamConfig,
	VerifyConfig,
	VisionConfig,
)
from ada.agent.llm import make_llm_callable
from ada.agent.nodes import plan_node, respond_node
from ada.agent.server import create_app
from ada.agent.stream_sink import StreamChunk, StreamContext, StreamSink
from ada.llm import ChatCompletionResult
from ada.registry import Profile


def _profile() -> Profile:
	return Profile(
		name="test",
		label="test",
		provider="openai",
		base_url="http://127.0.0.1:8080/v1",
		api_key="local",
	)


def _direct_config() -> AgentConfig:
	return AgentConfig(
		system_prompt="",
		routing=RoutingConfig(plan_min_chars=999, plan_keywords=()),
		plan=PlanConfig(enabled=False, prompt=""),
		respond=RespondConfig(include_plan_hint=False),
		verify=VerifyConfig(max_empty_retries=0),
		vision=VisionConfig(image_only_prompt=""),
	)


def _plan_config(*, plan_fallback_tags: bool = False) -> AgentConfig:
	return AgentConfig(
		system_prompt="",
		routing=RoutingConfig(plan_min_chars=1, plan_keywords=()),
		plan=PlanConfig(enabled=True, prompt="plan"),
		respond=RespondConfig(include_plan_hint=False),
		verify=VerifyConfig(max_empty_retries=0),
		vision=VisionConfig(image_only_prompt=""),
		stream=StreamConfig(plan_fallback_tags=plan_fallback_tags),
	)


class FakeClient:
	def chat(self, messages, max_tokens=1024):
		return "buffered"

	def chat_completion_stream(self, messages, *, on_delta, max_tokens=1024):
		for token in ("안", "녕"):
			on_delta(token)
		return ChatCompletionResult(content="안녕", tool_calls=None, finish_reason="stop")

	def close(self):
		pass


def _collect_chunks(sink: StreamSink) -> list[StreamChunk]:
	return sink.drain_pending()


def test_respond_node_streams_tokens_to_sink():
	sink = StreamSink()
	ctx = StreamContext(sink=sink)
	llm = make_llm_callable(_profile(), client_factory=lambda _p: FakeClient(), stream_context=ctx)
	node = respond_node(_direct_config(), llm, ctx)
	node(
		{
			"messages": [HumanMessage(content="hi")],
			"plan": "",
			"empty_retries": 0,
		}
	)
	chunks = _collect_chunks(sink)
	assert "".join(c.text for c in chunks) == "안녕"
	assert all(c.channel == "content" for c in chunks)
	assert ctx.allow_stream is False


def test_plan_node_streams_reasoning_channel():
	sink = StreamSink()
	ctx = StreamContext(sink=sink, plan_fallback_tags=False)
	llm = make_llm_callable(_profile(), client_factory=lambda _p: FakeClient(), stream_context=ctx)
	node = plan_node(_plan_config(plan_fallback_tags=False), llm, ctx)
	node(
		{
			"messages": [HumanMessage(content="design a system")],
			"plan": "",
			"empty_retries": 0,
		}
	)
	chunks = _collect_chunks(sink)
	assert chunks
	assert all(c.channel == "reasoning" for c in chunks)


def test_plan_node_fallback_tags_use_content_channel():
	sink = StreamSink()
	ctx = StreamContext(sink=sink, plan_fallback_tags=True)
	llm = make_llm_callable(_profile(), client_factory=lambda _p: FakeClient(), stream_context=ctx)
	node = plan_node(_plan_config(plan_fallback_tags=True), llm, ctx)
	node(
		{
			"messages": [HumanMessage(content="design a system")],
			"plan": "",
			"empty_retries": 0,
		}
	)
	chunks = _collect_chunks(sink)
	assert chunks
	assert all(c.channel == "content" for c in chunks)
	assert chunks[0].text.startswith("\n")


def test_stream_sink_finish_marks_done():
	sink = StreamSink()
	sink.push("a")
	sink.finish()
	chunk = sink.get()
	assert isinstance(chunk, StreamChunk)
	assert chunk.text == "a"
	assert sink.get() is None


def test_run_chat_completion_streaming_calls_finish():
	from ada.agent.openai_compat import run_chat_completion_streaming

	sink = StreamSink()
	with patch(
		"ada.agent.openai_compat.run_chat_completion",
		return_value="ok",
	):
		result = run_chat_completion_streaming([], lambda _m: "", sink)
	assert result == "ok"
	assert sink.get() is None


def test_sse_delta_fields_for_channels():
	from ada.agent.openai_compat import build_chat_completion_chunk

	reasoning = build_chat_completion_chunk(
		"m",
		"id",
		1,
		delta={"reasoning_content": "p"},
	)
	content = build_chat_completion_chunk(
		"m",
		"id",
		1,
		delta={"content": "c"},
	)
	assert reasoning["choices"][0]["delta"]["reasoning_content"] == "p"
	assert content["choices"][0]["delta"]["content"] == "c"


def test_stream_true_returns_sse_by_default():
	def fake_streaming(messages, llm_callable, stream_sink, config=None, stream_context=None):
		stream_sink.push("hi")
		stream_sink.finish()
		return "hi"

	app = create_app()
	with (
		patch("ada.agent.server.FORCE_NON_STREAM", False),
		patch("ada.agent.server.effective_model_id", return_value="test-model"),
		patch("ada.agent.server.run_chat_completion_streaming", side_effect=fake_streaming),
	):
		client = TestClient(app)
		with client.stream(
			"POST",
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [{"role": "user", "content": "ping"}],
				"stream": True,
			},
		) as resp:
			assert resp.status_code == 200
			assert "text/event-stream" in resp.headers["content-type"]
			body = "".join(resp.iter_text())
			assert "hi" in body
			assert "[DONE]" in body


def test_stream_true_buffered_when_force_non_stream_enabled():
	def fake_run(_messages, _llm, config=None, stream_context=None):
		return "buffered"

	app = create_app()
	with (
		patch("ada.agent.server.FORCE_NON_STREAM", True),
		patch("ada.agent.server.effective_model_id", return_value="test-model"),
		patch("ada.agent.server.run_chat_completion", side_effect=fake_run),
	):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [{"role": "user", "content": "ping"}],
				"stream": True,
			},
		)

	assert resp.status_code == 200
	assert resp.headers["content-type"].startswith("application/json")
	assert resp.json()["choices"][0]["message"]["content"] == "buffered"


def test_stream_true_include_usage_emits_usage_chunk():
	def fake_streaming(messages, llm_callable, stream_sink, config=None, stream_context=None):
		stream_sink.push("hi")
		stream_sink.finish()
		return "hi"

	app = create_app()
	with (
		patch("ada.agent.server.FORCE_NON_STREAM", False),
		patch("ada.agent.server.effective_model_id", return_value="test-model"),
		patch("ada.agent.server.run_chat_completion_streaming", side_effect=fake_streaming),
	):
		client = TestClient(app)
		with client.stream(
			"POST",
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [{"role": "user", "content": "ping"}],
				"stream": True,
				"stream_options": {"include_usage": True},
			},
		) as resp:
			assert resp.status_code == 200
			body = "".join(resp.iter_text())
			assert '"usage"' in body
			assert "[DONE]" in body
