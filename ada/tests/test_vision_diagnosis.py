from __future__ import annotations

from langchain_core.messages import HumanMessage

from ada.agent.config import AgentConfig, PlanConfig, RespondConfig, RoutingConfig, VerifyConfig, VisionConfig
from ada.agent.content import (
	content_has_image,
	content_is_empty,
	ensure_user_prompt,
	extract_text_from_content,
	parse_openai_content,
)
from ada.agent.graph import run_user_turn
from ada.agent.llm import _to_chat_messages
from ada.agent.openai_compat import openai_messages_to_langchain, split_history_and_user
from ada.llm import ChatMessage, LLMClient
from ada.registry import Profile
from fixtures.vision_fixtures import (
	TINY_PNG_B64,
	openai_user_image_only,
	openai_user_multimodal,
)


def test_parse_openai_content_preserves_image_url():
	content = parse_openai_content(openai_user_multimodal()["content"])
	assert isinstance(content, list)
	assert content_has_image(content)


def test_openai_to_langchain_keeps_multimodal_user_message():
	msgs = openai_messages_to_langchain([openai_user_multimodal()])
	assert len(msgs) == 1
	assert isinstance(msgs[0], HumanMessage)
	assert isinstance(msgs[0].content, list)
	assert content_has_image(msgs[0].content)


def test_split_history_returns_multimodal_user_content():
	history, user_content = split_history_and_user(
		[
			openai_user_multimodal("first"),
			{"role": "assistant", "content": "ok"},
			openai_user_multimodal("second"),
		]
	)
	assert len(history) == 2
	assert content_has_image(user_content)


def _empty_config() -> AgentConfig:
	return AgentConfig(
		system_prompt="",
		routing=RoutingConfig(),
		plan=PlanConfig(enabled=False),
		respond=RespondConfig(),
		verify=VerifyConfig(),
		vision=VisionConfig(),
	)


def test_run_user_turn_accepts_image_only():
	def fake_llm(messages):
		for message in reversed(messages):
			if isinstance(message, HumanMessage):
				assert isinstance(message.content, list)
				assert content_has_image(message.content)
				return "seen-image"
		return ""

	text, history = run_user_turn(
		parse_openai_content(openai_user_image_only()["content"]),
		[],
		fake_llm,
		config=_empty_config(),
	)
	assert text == "seen-image"
	assert len(history) == 2


def test_agent_llm_preserves_list_content():
	msgs = _to_chat_messages(
		[
			HumanMessage(
				content=[
					{"type": "text", "text": "hi"},
					{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"}},
				]
			)
		]
	)
	assert isinstance(msgs[0].content, list)
	assert msgs[0].content[1]["type"] == "image_url"


def test_llm_client_payload_accepts_multimodal_content():
	profile = Profile(
		name="test",
		label="test",
		provider="openai-compatible",
		base_url="http://127.0.0.1:8080/v1",
		model="test-model",
		api_key="local",
	)
	client = LLMClient(profile, api_key="local")
	messages = [
		ChatMessage(
			role="user",
			content=[
				{"type": "text", "text": "describe"},
				{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"}},
			],
		)
	]
	payload_messages = [{"role": m.role, "content": m.content} for m in messages]
	assert isinstance(payload_messages[0]["content"], list)
	client.close()


def test_ensure_user_prompt_adds_text_for_image_only():
	content = ensure_user_prompt(parse_openai_content(openai_user_image_only()["content"]))
	assert not content_is_empty(content)
	assert "Describe the image." in extract_text_from_content(content)
