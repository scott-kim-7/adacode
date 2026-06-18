from __future__ import annotations

from unittest.mock import patch

from ada.email.graph import run_email_draft, run_email_summarize


def test_run_email_summarize_uses_llm():
	calls: list[str] = []

	def fake_llm(messages):
		system = str(messages[0].content)
		calls.append(system)
		if "지시사항" in system:
			return "- 일정 정리"
		return "- 요청1\n- 요청2"

	result = run_email_summarize(
		{
			"message_id": "m1",
			"subject": "Hi",
			"body_text": "Ada please reply",
			"from_address": "user@example.com",
			"attachment_names": [],
		},
		fake_llm,
	)
	assert "- 요청1" in str(result.get("summary_text"))
	assert len(calls) == 2
	assert result.get("todo_items")


def test_run_email_summarize_can_skip_by_rule():
	def fake_llm(messages):
		raise AssertionError("LLM should not be called for summarize when skipped")

	result = run_email_summarize(
		{
			"message_id": "m2",
			"subject": "newsletter",
			"body_text": "content",
			"from_address": "noreply@example.com",
			"headers": {},
			"summary_skip_rules": [
				{"id": "r1", "name": "noreply", "enabled": True, "match": "from_noreply"}
			],
		},
		lambda messages: "- only instruction",
	)
	assert result.get("should_summarize") is False
	assert result.get("skip_rule_id") == "r1"


def test_run_email_summarize_skips_with_logic_all():
	result = run_email_summarize(
		{
			"message_id": "m3",
			"subject": "sale today",
			"body_text": "content",
			"from_address": "shop@example.com",
			"headers": {},
			"summary_skip_rules": [
				{
					"id": "r2",
					"name": "shop sale",
					"enabled": True,
					"logic": "all",
					"conditions": [
						{"match": "sender_domain", "pattern": "example.com"},
						{"match": "subject_contains", "pattern": "sale"},
					],
				}
			],
		},
		lambda messages: "- should not summarize",
	)
	assert result.get("should_summarize") is False
	assert result.get("skip_rule_id") == "r2"


def test_run_email_draft_uses_llm():
	def fake_llm(messages):
		return "확인했습니다."

	with patch("ada.email.graph.build_email_draft_graph") as mock_build:
		mock_build.return_value.invoke.return_value = {
			"draft_subject": "Re: Hi",
			"draft_body": "확인했습니다.",
			"confidence": 0.75,
			"safety_flags": [],
		}
		result = run_email_draft(
			{
				"subject": "Hi",
				"body_text": "please reply",
				"thread_context": [],
			},
			fake_llm,
		)
	assert result["draft_body"] == "확인했습니다."
