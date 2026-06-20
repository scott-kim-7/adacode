from __future__ import annotations

from pathlib import Path


def test_phase3_middleware_skip_patch():
	root = Path(__file__).resolve().parents[2]
	middleware = root / "web/open-webui/backend/open_webui/utils/middleware.py"
	if not middleware.is_file():
		return
	text = middleware.read_text()
	assert "_ada_agent_handles_context" in text
	assert "chat_web_search_handler" in text
	assert "tool_calls.clear()" in text


def test_phase3_ada_tools_execute_route():
	root = Path(__file__).resolve().parents[2]
	ada_router = root / "web/open-webui/backend/open_webui/routers/ada.py"
	if not ada_router.is_file():
		return
	text = ada_router.read_text()
	assert "/tools/execute" in text
