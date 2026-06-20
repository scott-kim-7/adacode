from __future__ import annotations

from unittest.mock import MagicMock, patch

from ada.llm import ChatMessage, LLMClient
from ada.registry import Profile


def test_llm_client_prefers_loaded_model_over_config_model_id():
	profile = Profile(
		name="chat",
		label="chat",
		provider="openai-compatible",
		base_url="http://127.0.0.1:8089/v1",
		api_key="local",
		model_id="mlx-coder",
	)
	client = LLMClient(profile, api_key="local")

	mock_resp = MagicMock()
	mock_resp.raise_for_status = MagicMock()
	mock_resp.json.return_value = {
		"choices": [
			{
				"message": {"content": "ok"},
				"finish_reason": "stop",
			}
		]
	}

	with (
		patch(
			"ada.openai_models.loaded_model_from_health",
			return_value="mlx-main",
		),
		patch.object(client._client, "post", return_value=mock_resp) as post,
	):
		result = client.chat_completion([ChatMessage(role="user", content="hi")])

	assert result.content == "ok"
	body = post.call_args.kwargs["json"]
	assert body["model"] == "mlx-main"


def test_llm_client_uses_config_model_id_when_nothing_loaded():
	profile = Profile(
		name="chat",
		label="chat",
		provider="openai-compatible",
		base_url="http://127.0.0.1:8089/v1",
		api_key="local",
		model_id="mlx-coder",
	)
	client = LLMClient(profile, api_key="local")

	mock_resp = MagicMock()
	mock_resp.raise_for_status = MagicMock()
	mock_resp.json.return_value = {
		"choices": [
			{
				"message": {"content": "ok"},
				"finish_reason": "stop",
			}
		]
	}

	with (
		patch("ada.openai_models.loaded_model_from_health", return_value=None),
		patch("ada.openai_models.list_model_ids", return_value=[]),
		patch.object(client._client, "post", return_value=mock_resp) as post,
	):
		result = client.chat_completion([ChatMessage(role="user", content="hi")])

	assert result.content == "ok"
	body = post.call_args.kwargs["json"]
	assert body["model"] == "mlx-coder"
