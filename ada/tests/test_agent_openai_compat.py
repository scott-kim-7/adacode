from __future__ import annotations

from ada.agent.config import AgentConfig, PlanConfig, RespondConfig, RoutingConfig, VerifyConfig
from ada.agent.openai_compat import (
	build_chat_completion_response,
	openai_messages_to_langchain,
	run_chat_completion,
	split_history_and_user,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


def _config() -> AgentConfig:
	return AgentConfig(
		system_prompt="",
		routing=RoutingConfig(plan_min_chars=50, plan_keywords=("plan",)),
		plan=PlanConfig(enabled=True, prompt="plan-only"),
		respond=RespondConfig(include_plan_hint=False),
		verify=VerifyConfig(max_empty_retries=1),
	)


def test_openai_messages_to_langchain_roles():
	msgs = openai_messages_to_langchain(
		[
			{"role": "system", "content": "sys"},
			{"role": "user", "content": "hi"},
			{"role": "assistant", "content": "hello"},
		]
	)
	assert isinstance(msgs[0], SystemMessage)
	assert isinstance(msgs[1], HumanMessage)
	assert isinstance(msgs[2], AIMessage)


def test_split_history_and_user():
	history, user_text = split_history_and_user(
		[
			{"role": "user", "content": "first"},
			{"role": "assistant", "content": "reply"},
			{"role": "user", "content": "second"},
		]
	)
	assert user_text == "second"
	assert len(history) == 2


def test_run_chat_completion_uses_main_graph():
	def fake_llm(messages):
		last = messages[-1]
		return f"echo:{last.content}"

	content = run_chat_completion(
		[{"role": "user", "content": "hello"}],
		fake_llm,
		config=_config(),
	)
	assert content == "echo:hello"


def test_build_chat_completion_response_shape():
	body = build_chat_completion_response("test-model", "ok")
	assert body["object"] == "chat.completion"
	assert body["model"] == "test-model"
	assert body["choices"][0]["message"]["content"] == "ok"
