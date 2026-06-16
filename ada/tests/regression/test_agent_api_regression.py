from __future__ import annotations

from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from ada.agent.openai_compat import build_chat_completion_response, run_chat_completion
from ada.agent.server import create_app
from fixtures.vision_fixtures import openai_user_image_only, openai_user_multimodal
from regression.conftest import regression_agent_config


def test_regression_chat_completion_response_openai_shape():
	body = build_chat_completion_response("test-model", "hello")
	assert body["object"] == "chat.completion"
	assert body["choices"][0]["message"]["role"] == "assistant"
	assert body["choices"][0]["message"]["content"] == "hello"
	assert body["choices"][0]["finish_reason"] == "stop"
	assert body["id"].startswith("chatcmpl-")


def test_regression_stream_true_returns_buffered_json_not_sse():
	app = create_app()

	def fake_run(_messages, _llm, config=None, stream_context=None):
		return "buffered"

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
			headers={"Authorization": "Bearer local"},
		)

	assert resp.status_code == 200
	assert resp.headers["content-type"].startswith("application/json")
	payload = resp.json()
	assert payload["choices"][0]["message"]["content"] == "buffered"


def test_regression_stream_true_returns_sse_by_default():
	app = create_app()

	def fake_streaming(messages, llm_callable, stream_sink, config=None, stream_context=None):
		stream_sink.push("tok")
		stream_sink.finish()
		return "tok"

	with (
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
			assert "tok" in body
			assert "[DONE]" in body


def test_regression_health_endpoint():
	app = create_app()
	client = TestClient(app)
	resp = client.get("/health")
	assert resp.status_code == 200
	assert resp.json()["status"] == "ok"
	assert "endpoint" in resp.json()


def test_regression_models_errors_when_mlx_unreachable():
	app = create_app()
	with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("down")):
		client = TestClient(app, raise_server_exceptions=False)
		resp = client.get("/v1/models", headers={"Authorization": "Bearer local"})
	assert resp.status_code == 503


def test_regression_text_chat_end_to_end_mocked():
	captured: list = []

	def fake_run(messages, _llm, config=None):
		captured.append(messages)
		return "assistant-reply"

	app = create_app()
	with patch("ada.agent.server.run_chat_completion", side_effect=fake_run):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [{"role": "user", "content": "hello"}],
			},
		)

	assert resp.status_code == 200
	assert resp.json()["choices"][0]["message"]["content"] == "assistant-reply"
	assert captured


def test_regression_multimodal_chat_end_to_end_mocked():
	captured: list = []

	def fake_run(messages, _llm, config=None):
		captured.append(messages)
		return "vision-reply"

	app = create_app()
	with patch("ada.agent.server.run_chat_completion", side_effect=fake_run):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [openai_user_multimodal()],
			},
		)

	assert resp.status_code == 200
	assert resp.json()["choices"][0]["message"]["content"] == "vision-reply"
	assert captured[0][0]["content"][1]["type"] == "image_url"


def test_regression_image_only_not_rejected():
	app = create_app()

	with patch("ada.agent.server.run_chat_completion", return_value="ok"):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			json={"model": "test", "messages": [openai_user_image_only()]},
		)

	assert resp.status_code == 200
	assert resp.json()["choices"][0]["message"]["content"] == "ok"


def test_regression_run_chat_completion_text_roundtrip():
	def fake_llm(messages):
		return "pong"

	cfg = regression_agent_config()
	assert (
		run_chat_completion([{"role": "user", "content": "ping"}], fake_llm, config=cfg) == "pong"
	)
