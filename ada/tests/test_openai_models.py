from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ada.openai_models import (
	NoLoadedModelError,
	effective_model_id,
	list_model_ids,
	loaded_model_from_health,
	resolve_model_id,
)


def test_list_model_ids_parses_openapi_response():
	mock_resp = MagicMock()
	mock_resp.raise_for_status = MagicMock()
	mock_resp.json.return_value = {
		"object": "list",
		"data": [{"id": "model-a", "object": "model"}, {"id": "model-b", "object": "model"}],
	}
	with patch("ada.openai_models.httpx.Client") as client_cls:
		client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
		assert list_model_ids("http://127.0.0.1:8080/v1") == ["model-a", "model-b"]


def test_resolve_model_id_uses_loaded_model_from_health():
	health_resp = MagicMock()
	health_resp.raise_for_status = MagicMock()
	health_resp.json.return_value = {"status": "healthy", "loaded_model": "server-loaded"}

	with patch("ada.openai_models.httpx.Client") as client_cls:
		client_cls.return_value.__enter__.return_value.get.return_value = health_resp
		assert resolve_model_id("http://127.0.0.1:8080/v1") == "server-loaded"


def test_effective_model_id_prefers_loaded_over_request():
	with patch("ada.openai_models.loaded_model_from_health", return_value="from-server"):
		assert (
			effective_model_id("http://127.0.0.1:8080/v1", "other-model")
			== "from-server"
		)


def test_effective_model_id_uses_request_when_not_loaded():
	with patch("ada.openai_models.loaded_model_from_health", return_value=None):
		assert effective_model_id("http://127.0.0.1:8080/v1", "user-picked") == "user-picked"


def test_resolve_model_id_raises_when_nothing_loaded():
	with (
		patch("ada.openai_models.loaded_model_from_health", return_value=None),
		patch("ada.openai_models.list_model_ids", side_effect=RuntimeError("no models")),
	):
		with pytest.raises(NoLoadedModelError):
			resolve_model_id("http://127.0.0.1:8080/v1")


def test_resolve_model_id_via_agent_base_uses_mlx_health():
	health_resp = MagicMock()
	health_resp.raise_for_status = MagicMock()
	health_resp.json.return_value = {
		"status": "healthy",
		"loaded_model": "mlx-loaded",
	}

	with patch("ada.openai_models.httpx.Client") as client_cls:
		client_cls.return_value.__enter__.return_value.get.return_value = health_resp
		got = resolve_model_id("http://127.0.0.1:9082/v1")
	assert got == "mlx-loaded"
	call_url = client_cls.return_value.__enter__.return_value.get.call_args[0][0]
	assert call_url == "http://127.0.0.1:8089/health"


def test_loaded_model_from_health_accepts_model_id():
	mock_resp = MagicMock()
	mock_resp.raise_for_status = MagicMock()
	mock_resp.json.return_value = {
		"status": "ok",
		"model_id": "mlx-community/Qwen3-VL-30B-A3B-Instruct-8bit, mlx-community/other",
	}
	with patch("ada.openai_models.httpx.Client") as client_cls:
		client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
		assert (
			loaded_model_from_health("http://127.0.0.1:8089/v1")
			== "mlx-community/Qwen3-VL-30B-A3B-Instruct-8bit"
		)


def test_loaded_model_from_health_uses_v1_models_for_litellm():
	health_resp = MagicMock()
	health_resp.raise_for_status = MagicMock()
	health_resp.json.return_value = {
		"healthy_count": 3,
		"healthy_endpoints": [
			{"model": "openai/mlx-community/Qwen3-VL-30B-A3B-Instruct-8bit"},
		],
	}
	models_resp = MagicMock()
	models_resp.raise_for_status = MagicMock()
	models_resp.json.return_value = {
		"object": "list",
		"data": [{"id": "mlx-vision", "object": "model"}],
	}

	def fake_get(url, *args, **kwargs):
		if url.endswith("/health"):
			return health_resp
		if url.endswith("/models"):
			return models_resp
		raise AssertionError(url)

	with patch("ada.openai_models.httpx.Client") as client_cls:
		client_cls.return_value.__enter__.return_value.get.side_effect = fake_get
		assert loaded_model_from_health("http://127.0.0.1:8089/v1") == "mlx-vision"


def test_loaded_model_from_health_returns_none_when_missing():
	mock_resp = MagicMock()
	mock_resp.raise_for_status = MagicMock()
	mock_resp.json.return_value = {"status": "healthy", "loaded_model": None}
	with patch("ada.openai_models.httpx.Client") as client_cls:
		client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
		assert loaded_model_from_health("http://127.0.0.1:8080/v1") is None
