from __future__ import annotations

from unittest.mock import patch

import pytest

from ada.eval.adapters import bfcl_adapter, mcpagent_adapter, swe_adapter, tau2_adapter, toolsandbox_adapter
from ada.eval.harness.results import validate_result_schema

pytestmark = pytest.mark.eval_smoke


def _mock_chat_response(content: str = "ok", tool_calls=None):
	return {
		"choices": [
			{
				"message": {
					"role": "assistant",
					"content": content,
					**({"tool_calls": tool_calls} if tool_calls else {}),
				}
			}
		]
	}


@patch("ada.eval.adapters.tau2_adapter.AgentEvalClient")
def test_tau2_adapter_offline(mock_client):
	instance = mock_client.return_value
	instance.chat.return_value = _mock_chat_response("ok")
	payload = tau2_adapter._fallback(2, "smoke")
	validate_result_schema(payload)
	assert payload["benchmark"] == "tau2"


@patch("ada.eval.adapters.bfcl_adapter.AgentEvalClient")
def test_bfcl_adapter_offline(mock_client):
	instance = mock_client.return_value
	instance.chat.return_value = _mock_chat_response(
		"",
		tool_calls=[{"id": "1", "function": {"name": "get_weather", "arguments": "{}"}}],
	)
	payload = bfcl_adapter._fallback(2, "smoke", "simple_python")
	validate_result_schema(payload)
	assert payload["benchmark"] == "bfcl"


@patch("ada.eval.adapters.swe_adapter.AgentEvalClient")
def test_swe_adapter_offline(mock_client):
	instance = mock_client.return_value
	instance.chat.return_value = _mock_chat_response("fix summary")
	payload = swe_adapter._fallback("django__django-11099", "smoke")
	validate_result_schema(payload)
	assert payload["benchmark"] == "swe"


@patch("ada.eval.adapters.toolsandbox_adapter.AgentEvalClient")
def test_toolsandbox_adapter_offline(mock_client):
	instance = mock_client.return_value
	instance.chat.return_value = _mock_chat_response(
		"",
		tool_calls=[{"id": "1", "function": {"name": "set_reminder", "arguments": "{}"}}],
	)
	payload = toolsandbox_adapter._fallback(2, "smoke")
	validate_result_schema(payload)
	assert payload["benchmark"] == "toolsandbox"


@patch("ada.eval.adapters.mcpagent_adapter.AgentEvalClient")
def test_mcpagent_adapter_offline(mock_client):
	instance = mock_client.return_value
	instance.chat.return_value = _mock_chat_response(
		"",
		tool_calls=[{"id": "1", "function": {"name": "search_docs", "arguments": "{}"}}],
	)
	payload = mcpagent_adapter._fallback(2, "smoke")
	validate_result_schema(payload)
	assert payload["benchmark"] == "mcpagent"
