from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from ada.agent.graph import build_simple_agent_graph, run_user_turn
from ada.agent.session import AgentSession
from fixtures.vision_fixtures import openai_user_multimodal
from regression.conftest import human_has_image, regression_agent_config


def test_regression_direct_path_single_llm_call():
	calls: list[str] = []

	def fake_llm(messages):
		calls.append("llm")
		last = messages[-1]
		return f"echo:{last.content}"

	cfg = regression_agent_config()
	run_turn = build_simple_agent_graph(fake_llm, config=cfg)
	assert run_turn([HumanMessage(content="hello")]) == "echo:hello"
	assert calls == ["llm"]


def test_regression_plan_path_two_llm_calls():
	stages: list[str] = []

	def fake_llm(messages):
		if messages[0].content == "plan-only":
			stages.append("plan")
			return "- step 1"
		stages.append("respond")
		return "final"

	cfg = regression_agent_config()
	run_turn = build_simple_agent_graph(fake_llm, config=cfg)
	assert run_turn([HumanMessage(content="make a plan for cache")]) == "final"
	assert stages == ["plan", "respond"]


def test_regression_empty_response_retry():
	attempts = {"count": 0}

	def fake_llm(_messages):
		attempts["count"] += 1
		return "" if attempts["count"] == 1 else "recovered"

	cfg = regression_agent_config()
	run_turn = build_simple_agent_graph(fake_llm, config=cfg)
	assert run_turn([HumanMessage(content="hi")]) == "recovered"
	assert attempts["count"] == 2


def test_regression_multi_turn_history():
	cfg = regression_agent_config()
	session = AgentSession(lambda _m: "ok", config=cfg)
	assert session.send("first") == "ok"
	assert session.send("second") == "ok"
	assert len(session.history) == 4
	assert isinstance(session.history[0], HumanMessage)
	assert isinstance(session.history[1], AIMessage)


def test_regression_vision_respond_receives_image():
	from ada.agent.openai_compat import run_chat_completion

	captured: list[list] = []

	def fake_llm(messages):
		captured.append(messages)
		return "seen"

	cfg = regression_agent_config()
	content = run_chat_completion([openai_user_multimodal("what color?")], fake_llm, config=cfg)
	assert content == "seen"
	assert human_has_image(captured[-1])


def test_regression_vision_plan_receives_image():
	captured: list[list] = []

	def fake_llm(messages):
		captured.append(messages)
		if messages[0].content == "plan-only":
			return "- step"
		return "final"

	from ada.agent.openai_compat import run_chat_completion

	cfg = regression_agent_config()
	content = run_chat_completion(
		[openai_user_multimodal("make a plan for this architecture redesign")],
		fake_llm,
		config=cfg,
	)
	assert content == "final"
	assert human_has_image(captured[0])


def test_regression_run_user_turn_text_history():
	cfg = regression_agent_config()

	def fake_llm(messages):
		last = messages[-1]
		return f"reply:{last.content}"

	text, history = run_user_turn("hi", [], fake_llm, config=cfg)
	assert text == "reply:hi"
	assert len(history) == 2
