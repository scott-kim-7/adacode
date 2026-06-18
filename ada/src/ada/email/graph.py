from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal, cast
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from ada.email.state import EmailState
from ada.email.summary_skip import evaluate_summary_skip


SUMMARIZE_SYSTEM = (
	"메일이 나에게 요청하는 사항을 bullet로 정리하세요. "
	"명시적 요청이 없으면 '명시적 요청 없음' 한 줄만 출력하세요."
)
DRAFT_SYSTEM = (
	"이메일 회신 초안을 작성하세요. 정중하고 간결하게, 한국어로 작성합니다."
)
INSTRUCTIONS_SYSTEM = (
	"이메일에서 Ada가 수행해야 할 지시사항만 bullet로 추출하세요. "
	"없으면 빈 문자열을 출력하세요."
)


def build_email_summarize_graph(llm_callable: Callable[[list], str]) -> Any:
	graph = StateGraph(EmailState)

	def prepare(state: EmailState) -> EmailState:
		return state

	def extract_instructions(state: EmailState) -> EmailState:
		prompt = (
			f"From: {state.get('from_address', '')}\n"
			f"Subject: {state.get('subject', '')}\n\n"
			f"{state.get('body_text', '')}"
		)
		text = llm_callable([SystemMessage(content=INSTRUCTIONS_SYSTEM), HumanMessage(content=prompt)]).strip()
		items: list[dict[str, object]] = []
		for raw in text.splitlines():
			line = raw.strip().lstrip("-").strip()
			if line:
				items.append({"title": line, "detail": "", "priority": "normal", "due_hint": None})
		return {**state, "todo_items": items}

	def push_todo_queue(state: EmailState) -> EmailState:
		return state

	def check_summary_skip(state: EmailState) -> EmailState:
		rule_id = evaluate_summary_skip(
			from_address=str(state.get("from_address") or ""),
			subject=str(state.get("subject") or ""),
			headers=cast(dict[str, str], state.get("headers") or {}),
			rules=cast(list[dict[str, object]], state.get("summary_skip_rules") or []),
		)
		return {**state, "should_summarize": rule_id is None, "skip_rule_id": rule_id}

	def summarize(state: EmailState) -> EmailState:
		names = state.get("attachment_names") or []
		prompt = (
			f"From: {state.get('from_address', '')}\n"
			f"Subject: {state.get('subject', '')}\n"
			f"Attachments: {', '.join(names) if names else 'none'}\n\n"
			f"{state.get('body_text', '')}"
		)
		text = llm_callable(
			[
				SystemMessage(content=SUMMARIZE_SYSTEM),
				HumanMessage(content=prompt),
			]
		)
		return {
			**state,
			"summary_text": text.strip(),
			"confidence": 0.8,
			"safety_flags": [],
		}

	def skip_summary(state: EmailState) -> EmailState:
		return {**state, "summary_text": "", "should_summarize": False}

	def route_after_skip_check(state: EmailState) -> Literal["summarize_requests", "skip_summary"]:
		return "summarize_requests" if bool(state.get("should_summarize", True)) else "skip_summary"

	def finalize(state: EmailState) -> EmailState:
		return state

	graph.add_node("prepare_email_context", prepare)
	graph.add_node("extract_ada_instructions", extract_instructions)
	graph.add_node("push_todo_queue", push_todo_queue)
	graph.add_node("check_summary_skip", check_summary_skip)
	graph.add_node("summarize_requests", summarize)
	graph.add_node("skip_summary", skip_summary)
	graph.add_node("finalize_inbox_item", finalize)
	graph.add_edge(START, "prepare_email_context")
	graph.add_edge("prepare_email_context", "extract_ada_instructions")
	graph.add_edge("extract_ada_instructions", "push_todo_queue")
	graph.add_edge("push_todo_queue", "check_summary_skip")
	graph.add_conditional_edges("check_summary_skip", route_after_skip_check)
	graph.add_edge("summarize_requests", "finalize_inbox_item")
	graph.add_edge("skip_summary", "finalize_inbox_item")
	graph.add_edge("finalize_inbox_item", END)
	return graph.compile()


def build_email_draft_graph(llm_callable: Callable[[list], str]) -> Any:
	graph = StateGraph(EmailState)

	def prepare(state: EmailState) -> EmailState:
		return state

	def draft(state: EmailState) -> EmailState:
		context = state.get("thread_context") or []
		latest = str(state.get("body_text") or "").strip()
		prompt = (
			f"Latest message:\n{latest}\n\n"
			f"Thread context:\n{json.dumps(context, ensure_ascii=True)[:4000]}"
		)
		body = llm_callable(
			[
				SystemMessage(content=DRAFT_SYSTEM),
				HumanMessage(content=prompt),
			]
		)
		subject = str(state.get("subject") or "Re: Ada response")
		if not subject.lower().startswith("re:"):
			subject = f"Re: {subject}"
		return {**state, "draft_subject": subject, "draft_body": body.strip(), "confidence": 0.75, "safety_flags": []}

	def finalize(state: EmailState) -> EmailState:
		return state

	graph.add_node("prepare_reply_context", prepare)
	graph.add_node("draft_reply", draft)
	graph.add_node("finalize_draft", finalize)
	graph.add_edge(START, "prepare_reply_context")
	graph.add_edge("prepare_reply_context", "draft_reply")
	graph.add_edge("draft_reply", "finalize_draft")
	graph.add_edge("finalize_draft", END)
	return graph.compile()


def run_email_summarize(state: EmailState, llm_callable: Callable[[list], str]) -> EmailState:
	compiled = build_email_summarize_graph(llm_callable)
	result = compiled.invoke(state)
	return dict(result)


def run_email_draft(state: EmailState, llm_callable: Callable[[list], str]) -> EmailState:
	compiled = build_email_draft_graph(llm_callable)
	result = compiled.invoke(state)
	return dict(result)
