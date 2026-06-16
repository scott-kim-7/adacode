from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ada.agent.config import AgentConfig
from ada.agent.content import UserContent, extract_text_from_content
from ada.agent.state import AgentState, Route
from ada.agent.stream_sink import StreamContext


def _latest_user_content(messages: list[BaseMessage]) -> UserContent:
	for message in reversed(messages):
		if isinstance(message, HumanMessage):
			content = message.content
			if isinstance(content, list):
				return content
			return content if isinstance(content, str) else str(content)
	return ""


def _latest_user_text(messages: list[BaseMessage]) -> str:
	return extract_text_from_content(_latest_user_content(messages)).strip()


def prepare_node(config: AgentConfig) -> Callable[[AgentState], dict]:
	def prepare(state: AgentState) -> dict:
		updates: dict = {
			"route": "direct",
			"plan": "",
			"draft": "",
			"empty_retries": state.get("empty_retries", 0),
		}
		if not config.system_prompt:
			return updates
		messages = state.get("messages") or []
		if messages and isinstance(messages[0], SystemMessage):
			return updates
		return {
			**updates,
			"messages": [SystemMessage(content=config.system_prompt)],
		}

	return prepare


def route_node(config: AgentConfig) -> Callable[[AgentState], dict]:
	keywords = [keyword.lower() for keyword in config.routing.plan_keywords]

	def route(state: AgentState) -> dict:
		if not config.plan.enabled:
			return {"route": "direct"}
		user_text = _latest_user_text(state.get("messages") or [])
		lowered = user_text.lower()
		if len(user_text) >= config.routing.plan_min_chars:
			return {"route": "plan"}
		if any(keyword in lowered for keyword in keywords):
			return {"route": "plan"}
		return {"route": "direct"}

	return route


def plan_node(
	config: AgentConfig,
	llm_callable: Callable[[list[BaseMessage]], str],
	stream_context: StreamContext | None = None,
) -> Callable[[AgentState], dict]:
	def plan(state: AgentState) -> dict:
		user_content = _latest_user_content(state.get("messages") or [])
		plan_messages = [
			SystemMessage(content=config.plan.prompt),
			HumanMessage(content=user_content),
		]
		if stream_context is not None:
			stream_context.begin_plan_stream()
		try:
			plan_text = llm_callable(plan_messages).strip()
		finally:
			if stream_context is not None:
				stream_context.end_llm_stream()
		return {"plan": plan_text}

	return plan


def respond_node(
	config: AgentConfig,
	llm_callable: Callable[[list[BaseMessage]], str],
	stream_context: StreamContext | None = None,
) -> Callable[[AgentState], dict]:
	def respond(state: AgentState) -> dict:
		messages = list(state.get("messages") or [])
		plan_text = (state.get("plan") or "").strip()
		if plan_text and config.respond.include_plan_hint:
			messages = [
				*messages,
				SystemMessage(content=f"Internal plan (do not repeat verbatim):\n{plan_text}"),
			]
		retries = state.get("empty_retries", 0)
		if retries > 0:
			messages = [
				*messages,
				SystemMessage(content="Your previous answer was empty. Provide a helpful reply now."),
			]
		if stream_context is not None:
			stream_context.begin_respond_stream(had_plan=bool(plan_text))
		try:
			draft = llm_callable(messages).strip()
		finally:
			if stream_context is not None:
				stream_context.end_llm_stream()
		return {"draft": draft}

	return respond


def finalize_node(config: AgentConfig) -> Callable[[AgentState], dict]:
	def finalize(state: AgentState) -> dict:
		draft = (state.get("draft") or "").strip()
		if draft:
			return {"messages": [AIMessage(content=draft)], "draft": ""}
		fallback = "(응답을 생성하지 못했습니다. MLX 서버 상태를 확인해 주세요.)"
		return {"messages": [AIMessage(content=fallback)], "draft": ""}

	return finalize


def bump_retry_node() -> Callable[[AgentState], dict]:
	def bump_retry(state: AgentState) -> dict:
		return {"empty_retries": state.get("empty_retries", 0) + 1}

	return bump_retry


def route_decision(state: AgentState) -> Route:
	return state.get("route") or "direct"


def respond_decision(config: AgentConfig) -> Callable[[AgentState], str]:
	def decide(state: AgentState) -> str:
		draft = (state.get("draft") or "").strip()
		if draft:
			return "finalize"
		retries = state.get("empty_retries", 0)
		if retries < config.verify.max_empty_retries:
			return "retry"
		return "finalize"

	return decide
