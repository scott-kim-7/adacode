from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from ada.agent.graph import build_simple_agent_graph, run_user_turn
from ada.agent.session import AgentSession


def test_build_simple_agent_graph():
	def fake_llm(messages):
		last = messages[-1]
		assert isinstance(last, HumanMessage)
		return f"echo:{last.content}"

	run_turn = build_simple_agent_graph(fake_llm)
	result = run_turn([HumanMessage(content="hello")])
	assert result == "echo:hello"


def test_run_user_turn_accumulates_history():
	def fake_llm(messages):
		last = messages[-1]
		return f"reply:{last.content}"

	text, history = run_user_turn("hi", [], fake_llm)
	assert text == "reply:hi"
	assert len(history) == 2
	assert isinstance(history[0], HumanMessage)
	assert isinstance(history[1], AIMessage)


def test_agent_session_send_and_reset():
	session = AgentSession(lambda _m: "ok")
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

	session = AgentSession(fake_llm)
	session.load_history([("a", "b"), ("c", "d")])
	session.send("e")
	assert calls[-1] == 5
