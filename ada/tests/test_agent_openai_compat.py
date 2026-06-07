from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ada.agent.config import AgentConfig, PlanConfig, RespondConfig, RoutingConfig, VerifyConfig, VisionConfig
from ada.agent.content import (
	content_has_image,
	content_is_empty,
	ensure_user_prompt,
	extract_text_from_content,
	parse_openai_content,
)
from ada.agent.graph import run_user_turn
from ada.agent.openai_compat import (
	build_chat_completion_response,
	openai_messages_to_langchain,
	run_chat_completion,
	split_history_and_user,
)
from fixtures.vision_fixtures import (
	openai_history_with_prior_image,
	openai_user_image_only,
	openai_user_multimodal,
)


def _config(**overrides) -> AgentConfig:
	base = AgentConfig(
		system_prompt="",
		routing=RoutingConfig(plan_min_chars=50, plan_keywords=("plan",)),
		plan=PlanConfig(enabled=True, prompt="plan-only"),
		respond=RespondConfig(include_plan_hint=False),
		verify=VerifyConfig(max_empty_retries=1),
		vision=VisionConfig(image_only_prompt="Describe the image."),
	)
	if not overrides:
		return base
	return AgentConfig(
		system_prompt=overrides.get("system_prompt", base.system_prompt),
		routing=overrides.get("routing", base.routing),
		plan=overrides.get("plan", base.plan),
		respond=overrides.get("respond", base.respond),
		verify=overrides.get("verify", base.verify),
		vision=overrides.get("vision", base.vision),
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


def test_parse_openai_content_text_and_image():
	content = parse_openai_content(openai_user_multimodal()["content"])
	assert isinstance(content, list)
	assert len(content) == 2
	assert content_has_image(content)


def test_parse_openai_content_string_unchanged():
	assert parse_openai_content("hello") == "hello"


def test_content_is_empty_cases():
	assert content_is_empty("")
	assert content_is_empty("   ")
	assert not content_is_empty("hi")
	assert not content_is_empty(parse_openai_content(openai_user_image_only()["content"]))


def test_split_history_preserves_prior_image():
	history, user_content = split_history_and_user(openai_history_with_prior_image())
	assert len(history) == 2
	assert isinstance(history[0], HumanMessage)
	assert content_has_image(history[0].content)
	assert content_has_image(user_content)


def test_split_history_and_user_text_turn():
	history, user_content = split_history_and_user(
		[
			{"role": "user", "content": "first"},
			{"role": "assistant", "content": "reply"},
			{"role": "user", "content": "second"},
		]
	)
	assert user_content == "second"
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


def test_run_chat_completion_multimodal():
	captured: list[list] = []

	def fake_llm(messages):
		captured.append(messages)
		return "ok"

	content = run_chat_completion([openai_user_multimodal()], fake_llm, config=_config())
	assert content == "ok"
	last_user = captured[-1][-1]
	assert isinstance(last_user, HumanMessage)
	assert content_has_image(last_user.content)


def test_build_chat_completion_response_shape():
	body = build_chat_completion_response("test-model", "ok")
	assert body["object"] == "chat.completion"
	assert body["choices"][0]["message"]["content"] == "ok"


def test_ensure_user_prompt_image_only():
	content = ensure_user_prompt(parse_openai_content(openai_user_image_only()["content"]))
	assert extract_text_from_content(content) == "Describe the image."


def _human_has_image(messages: list) -> bool:
	for message in messages:
		if isinstance(message, HumanMessage) and isinstance(message.content, list):
			if content_has_image(message.content):
				return True
	return False


def test_respond_receives_image_in_messages():
	captured: list[list] = []

	def fake_llm(messages):
		captured.append(messages)
		return "answer"

	run_chat_completion([openai_user_multimodal("what color?")], fake_llm, config=_config())
	assert _human_has_image(captured[-1])


def test_plan_receives_image_when_route_plan():
	captured: list[list] = []

	def fake_llm(messages):
		captured.append(messages)
		if messages[0].content == "plan-only":
			return "- step"
		return "final"

	content = run_chat_completion(
		[openai_user_multimodal("make a plan for this architecture redesign")],
		fake_llm,
		config=_config(),
	)
	assert content == "final"
	plan_call = captured[0]
	assert _human_has_image(plan_call)


def test_run_user_turn_multimodal_history_length():
	def fake_llm(_messages):
		return "ok"

	_, history = run_user_turn(
		parse_openai_content(openai_user_multimodal()["content"]),
		[],
		fake_llm,
		config=_config(),
	)
	assert len(history) == 2
	assert isinstance(history[0], HumanMessage)
	assert isinstance(history[1], AIMessage)
