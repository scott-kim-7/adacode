from __future__ import annotations

from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from ada.agent.openai_compat import build_chat_completion_response, run_chat_completion
from ada.agent.server import create_app
from fixtures.vision_fixtures import openai_user_image_only, openai_user_multimodal
from regression.conftest import regression_agent_config


def test_regression_chat_completion_response_openai_shape():
	body = build_chat_completion_response("mlx-community/Qwen3-VL-32B-Instruct-8bit", "hello")
	assert body["object"] == "chat.completion"
	assert body["choices"][0]["message"]["role"] == "assistant"
	assert body["choices"][0]["message"]["content"] == "hello"
	assert body["choices"][0]["finish_reason"] == "stop"
	assert body["id"].startswith("chatcmpl-")


def test_regression_stream_true_returns_buffered_json_not_sse():
	app = create_app()

	def fake_run(_messages, _llm, config=None):
		return "buffered"

	with patch("ada.agent.server.run_chat_completion", side_effect=fake_run):
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


def test_regression_health_endpoint():
	app = create_app()
	client = TestClient(app)
	resp = client.get("/health")
	assert resp.status_code == 200
	assert resp.json()["status"] == "ok"
	assert "model" in resp.json()


def test_regression_models_fallback_when_mlx_unreachable():
	app = create_app()
	with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("down")):
		client = TestClient(app)
		resp = client.get("/v1/models", headers={"Authorization": "Bearer local"})
	assert resp.status_code == 200
	data = resp.json()
	assert data["object"] == "list"
	assert len(data["data"]) >= 1


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
