from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from ada.agent.config import AgentConfig, PlanConfig, RespondConfig, RoutingConfig, ToolsConfig, VerifyConfig, VisionConfig

pytestmark = pytest.mark.regression


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
	for item in items:
		path = str(item.fspath).replace("\\", "/")
		if "/regression/" in path and "/regression/eval/" not in path:
			item.add_marker(pytest.mark.regression)


def regression_agent_config(**overrides) -> AgentConfig:
	base = AgentConfig(
		system_prompt="",
		routing=RoutingConfig(plan_min_chars=50, plan_keywords=("plan", "설계")),
		plan=PlanConfig(enabled=True, prompt="plan-only"),
		respond=RespondConfig(include_plan_hint=False),
		verify=VerifyConfig(max_empty_retries=1),
		vision=VisionConfig(image_only_prompt="Describe the image."),
		tools=ToolsConfig(max_rounds=10, timeout_sec=300),
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
		tools=overrides.get("tools", base.tools),
	)


def human_has_image(messages: list) -> bool:
	from ada.agent.content import content_has_image

	for message in messages:
		if isinstance(message, HumanMessage) and isinstance(message.content, list):
			if content_has_image(message.content):
				return True
	return False
