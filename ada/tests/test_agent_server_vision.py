from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from ada.agent.server import create_app
from fixtures.vision_fixtures import openai_user_image_only, openai_user_multimodal


def test_chat_completions_multimodal_calls_graph():
	captured: list = []

	def fake_run(messages, metadata, chat_llm, tool_llm, config=None, stream_context=None, vault_session=None, openai_tools=None):
		captured.append(messages)
		return "vision-ok"

	app = create_app()
	with patch("ada.agent.server.run_unified_chat_completion", side_effect=fake_run):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [openai_user_multimodal()],
				"stream": False,
			},
			headers={"Authorization": "Bearer local"},
		)

	assert resp.status_code == 200
	assert resp.json()["choices"][0]["message"]["content"] == "vision-ok"
	assert captured
	assert captured[0][0]["content"][1]["type"] == "image_url"


def test_chat_completions_image_only_not_400():
	app = create_app()

	def fake_run(_messages, _metadata, _chat_llm, _tool_llm, config=None, stream_context=None, vault_session=None, openai_tools=None):
		return "ok"

	with patch("ada.agent.server.run_unified_chat_completion", side_effect=fake_run):
		client = TestClient(app)
		resp = client.post(
			"/v1/chat/completions",
			json={
				"model": "test",
				"messages": [openai_user_image_only()],
			},
			headers={"Authorization": "Bearer local"},
		)

	assert resp.status_code == 200
	assert resp.json()["choices"][0]["message"]["content"] == "ok"
