from __future__ import annotations

import yaml

from ada.agent.config import load_agent_config
from ada.agent.content import content_has_image, parse_openai_content
from ada.agent.openai_compat import openai_messages_to_langchain, split_history_and_user
from ada.agent.llm import _to_chat_messages
from ada.paths import ada_root
from ada.ports import DEFAULT_AGENT_PORT
from ada.registry import get_profile, load_registry
from fixtures.vision_fixtures import (
	TINY_PNG_B64,
	openai_history_with_prior_image,
	openai_user_image_only,
	openai_user_multimodal,
)
from langchain_core.messages import HumanMessage


def test_regression_agent_yaml_loads_vision_section():
	cfg = load_agent_config()
	assert cfg.vision.image_only_prompt
	assert cfg.plan.enabled is True
	assert cfg.verify.max_empty_retries >= 0


def test_regression_model_registry_chat_profile_openapi():
	reg = load_registry()
	profile = get_profile(reg, "chat_profile")
	assert profile.base_url.endswith("/v1")
	assert "127.0.0.1:8080" in profile.base_url


def test_regression_docker_compose_points_to_agent_api():
	repo_root = ada_root().parent
	compose = yaml.safe_load((repo_root / "web" / "docker-compose.yml").read_text(encoding="utf-8"))
	env = compose["services"]["open-webui"]["environment"]
	assert f":{DEFAULT_AGENT_PORT}" in env["OPENAI_API_BASE_URL"]
	assert env["ENABLE_DIRECT_CONNECTIONS"] == "false"


def test_regression_multimodal_content_never_stripped_in_compat():
	content = parse_openai_content(openai_user_multimodal()["content"])
	assert isinstance(content, list)
	assert content_has_image(content)

	msgs = openai_messages_to_langchain([openai_user_multimodal()])
	assert isinstance(msgs[0].content, list)
	assert content_has_image(msgs[0].content)


def test_regression_history_preserves_prior_images():
	history, user_content = split_history_and_user(openai_history_with_prior_image())
	assert len(history) == 2
	assert content_has_image(history[0].content)
	assert content_has_image(user_content)


def test_regression_llm_payload_preserves_image_url():
	msgs = _to_chat_messages(
		[
			HumanMessage(
				content=[
					{"type": "text", "text": "describe"},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"},
					},
				]
			)
		]
	)
	payload = [{"role": m.role, "content": m.content} for m in msgs]
	assert payload[0]["content"][1]["type"] == "image_url"


def test_regression_image_only_gets_default_prompt():
	from ada.agent.content import ensure_user_prompt, extract_text_from_content

	content = ensure_user_prompt(parse_openai_content(openai_user_image_only()["content"]))
	assert "Describe the image." in extract_text_from_content(content)
