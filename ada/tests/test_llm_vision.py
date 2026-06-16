from __future__ import annotations

from unittest.mock import MagicMock, patch

from ada.llm import ChatMessage, LLMClient
from ada.registry import Profile
from fixtures.vision_fixtures import TINY_PNG_B64


def _profile() -> Profile:
	return Profile(
		name="test",
		label="test",
		provider="openai-compatible",
		base_url="http://127.0.0.1:8080/v1",
		api_key="local",
	)


def _mock_response(content: str) -> MagicMock:
	response = MagicMock()
	response.raise_for_status = MagicMock()
	response.json.return_value = {"choices": [{"message": {"content": content}}]}
	return response


def test_llm_client_sends_multimodal_json():
	profile = _profile()
	mock_client = MagicMock()
	mock_client.post.return_value = _mock_response("red")

	with patch("ada.openai_models.resolve_model_id", return_value="test-model"):
		client = LLMClient(profile, api_key="local")
		client._client = mock_client
		content = [
			{"type": "text", "text": "describe"},
			{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"}},
		]
		client.chat([ChatMessage(role="user", content=content)])

	body = mock_client.post.call_args.kwargs["json"]
	assert isinstance(body["messages"][0]["content"], list)
	assert body["messages"][0]["content"][1]["type"] == "image_url"


def test_llm_client_string_content_unchanged():
	profile = _profile()
	mock_client = MagicMock()
	mock_client.post.return_value = _mock_response("hi")

	with patch("ada.openai_models.resolve_model_id", return_value="test-model"):
		client = LLMClient(profile, api_key="local")
		client._client = mock_client
		client.chat([ChatMessage(role="user", content="hello")])

	body = mock_client.post.call_args.kwargs["json"]
	assert body["messages"][0]["content"] == "hello"


def test_llm_client_timeout_default_300(monkeypatch):
	monkeypatch.delenv("ADA_LLM_TIMEOUT", raising=False)
	profile = _profile()
	client = LLMClient(profile, api_key="local")
	assert client._client.timeout.read == 300.0
	client.close()
