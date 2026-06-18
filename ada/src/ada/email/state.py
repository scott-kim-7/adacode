from __future__ import annotations

from typing import TypedDict


class EmailState(TypedDict, total=False):
	message_id: str
	thread_id: str
	account_id: str
	subject: str
	body_text: str
	from_address: str
	attachment_names: list[str]
	headers: dict[str, str]
	summary_skip_rules: list[dict[str, object]]
	should_summarize: bool
	skip_rule_id: str | None
	thread_snippet: str | None
	summary_text: str | None
	confidence: float | None
	safety_flags: list[str]
	todo_items: list[dict[str, object]]
	draft_subject: str | None
	draft_body: str | None
	action_id: int | None
	thread_context: list[dict[str, object]]
