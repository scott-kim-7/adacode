from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from ada.agent.config import AgentConfig, PlanConfig, RespondConfig, RoutingConfig, VerifyConfig
from ada.agent.graph import build_simple_agent_graph, run_user_turn
from ada.agent.nodes import route_node
from ada.agent.session import AgentSession


def _config(**overrides) -> AgentConfig:
	base = AgentConfig(
		system_prompt="",
		routing=RoutingConfig(plan_min_chars=50, plan_keywords=("plan", "설계")),
		plan=PlanConfig(enabled=True, prompt="plan-only"),
		respond=RespondConfig(include_plan_hint=False),
		verify=VerifyConfig(max_empty_retries=1),
	)
	if not overrides:
		return base
	return AgentConfig(
		system_prompt=overrides.get("system_prompt", base.system_prompt),
		routing=overrides.get("routing", base.routing),
		plan=overrides.get("plan", base.plan),
		respond=overrides.get("respond", base.respond),
		verify=overrides.get("verify", base.verify),
	)


def test_build_simple_agent_graph_direct():
	calls: list[str] = []

	def fake_llm(messages):
		last = messages[-1]
		calls.append(type(last).__name__)
		return f"echo:{last.content}"

	run_turn = build_simple_agent_graph(fake_llm, config=_config())
	result = run_turn([HumanMessage(content="hello")])
	assert result == "echo:hello"
	assert calls == ["HumanMessage"]


def test_route_node_plan_keyword():
	cfg = _config()
	route = route_node(cfg)
	state = {"messages": [HumanMessage(content="please make a plan for this")]}
	assert route(state)["route"] == "plan"


def test_route_node_direct_short():
	cfg = _config()
	route = route_node(cfg)
	state = {"messages": [HumanMessage(content="hi")]}
	assert route(state)["route"] == "direct"


def test_plan_path_calls_llm_twice():
	stages: list[str] = []

	def fake_llm(messages):
		if messages[0].content == "plan-only":
			stages.append("plan")
			return "- step 1\n- step 2"
		stages.append("respond")
		return "final answer"

	run_turn = build_simple_agent_graph(fake_llm, config=_config())
	result = run_turn([HumanMessage(content="make a plan for cache")])
	assert result == "final answer"
	assert stages == ["plan", "respond"]


def test_empty_response_retries_then_fallback():
	attempts = {"count": 0}

	def fake_llm(_messages):
		attempts["count"] += 1
		if attempts["count"] == 1:
			return ""
		return "recovered"

	run_turn = build_simple_agent_graph(fake_llm, config=_config())
	result = run_turn([HumanMessage(content="hi")])
	assert result == "recovered"
	assert attempts["count"] == 2


def test_run_user_turn_accumulates_history():
	def fake_llm(messages):
		last = messages[-1]
		return f"reply:{last.content}"

	text, history = run_user_turn("hi", [], fake_llm, config=_config())
	assert text == "reply:hi"
	assert len(history) == 2
	assert isinstance(history[0], HumanMessage)
	assert isinstance(history[1], AIMessage)


def test_agent_session_send_and_reset():
	session = AgentSession(lambda _m: "ok", config=_config())
	assert session.send("first") == "ok"
	assert session.send("second") == "ok"
	assert len(session.history) == 4
	session.reset()
	assert session.history == []


def test_agent_session_load_history():
	calls: list[int] = []

	def fake_llm(messages):
		calls.append(len(messages))
		return "done"

	session = AgentSession(fake_llm, config=_config())
	session.load_history([("a", "b"), ("c", "d")])
	session.send("e")
	assert calls[-1] == 5
