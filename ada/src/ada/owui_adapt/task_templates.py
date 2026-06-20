from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

# OWUI TASKS constants (open_webui/constants.py v0.6.42)
TASK_TITLE_GENERATION = "title_generation"
TASK_TAGS_GENERATION = "tags_generation"
TASK_FOLLOW_UP_GENERATION = "follow_up_generation"
TASK_AUTOCOMPLETE_GENERATION = "autocomplete_generation"
TASK_QUERY_GENERATION = "query_generation"

SUPPORTED_TASK_KINDS = frozenset(
	{
		TASK_TITLE_GENERATION,
		TASK_TAGS_GENERATION,
		TASK_FOLLOW_UP_GENERATION,
		TASK_AUTOCOMPLETE_GENERATION,
		TASK_QUERY_GENERATION,
	}
)

DEFAULT_TITLE_PROMPT_TEMPLATE = """### Task:
Generate a concise, 3-5 word title with an emoji summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Use emojis that enhance understanding of the topic, but avoid quotation marks or special formatting.
- Write the title in the chat's primary language; default to English if multilingual.
- Prioritize accuracy over excessive creativity; keep it clear and simple.
- Your entire response must consist solely of the JSON object, without any introductory or concluding text.
### Output:
JSON format: { "title": "your concise title here" }
### Chat History:
<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""

DEFAULT_TAGS_PROMPT_TEMPLATE = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.
### Guidelines:
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }
### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

DEFAULT_FOLLOW_UP_PROMPT_TEMPLATE = """### Task:
Suggest 3-5 relevant follow-up questions or prompts that the user might naturally ask next in this conversation as a **user**, based on the chat history.
### Guidelines:
- Write all follow-up questions from the user's point of view, directed to the assistant.
- Use the conversation's primary language; default to English if multilingual.
### Output:
JSON format: { "follow_ups": ["Question 1?", "Question 2?", "Question 3?"] }
### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

DEFAULT_AUTOCOMPLETE_PROMPT_TEMPLATE = """### Task:
You are an autocompletion system. Continue the text in `<text>` based on the **completion type** in `<type>` and the given language.
### Instructions:
1. Analyze `<text>` for context and meaning.
2. Start as if you are directly continuing `<text>`. Do **not** repeat, paraphrase, or respond as a model.
### Output Rules:
- Respond only in JSON format: `{ "text": "<your_completion>" }`.
### Input:
<type>{{TYPE}}</type>
<text>{{prompt}}</text>
### Chat History:
<chat_history>
{{MESSAGES:END:4}}
</chat_history>"""


def _format_message_line(message: dict[str, Any]) -> str:
	role = str(message.get("role") or "user").upper()
	content = message.get("content")
	if isinstance(content, list):
		parts: list[str] = []
		for item in content:
			if isinstance(item, dict) and item.get("type") == "text":
				parts.append(str(item.get("text") or ""))
		text = "\n".join(parts)
	elif content is None:
		text = ""
	else:
		text = str(content)
	return f"{role}: {text.strip()}"


def format_messages(messages: list[dict[str, Any]]) -> str:
	lines = [_format_message_line(m) for m in messages if isinstance(m, dict)]
	return "\n".join(line for line in lines if line.strip())


def _slice_messages(messages: list[dict[str, Any]], spec: str) -> list[dict[str, Any]]:
	if spec == "MESSAGES":
		return messages
	parts = spec.split(":")
	if len(parts) == 3 and parts[0] == "MESSAGES" and parts[1] == "END":
		count = int(parts[2])
		return messages[-count:] if count > 0 else messages
	if len(parts) == 3 and parts[0] == "MESSAGES" and parts[1] == "START":
		count = int(parts[2])
		return messages[:count] if count > 0 else messages
	return messages


def replace_messages_variable(template: str, messages: list[dict[str, Any]]) -> str:
	def replacement(match: re.Match[str]) -> str:
		full = match.group(0)
		if full == "{{MESSAGES}}":
			return format_messages(messages)
		start_len = match.group(1)
		end_len = match.group(2)
		if start_len is not None:
			return format_messages(messages[: int(start_len)])
		if end_len is not None:
			return format_messages(messages[-int(end_len) :])
		return format_messages(messages)

	pattern = r"\{\{MESSAGES\}\}|\{\{MESSAGES:START:(\d+)\}\}|\{\{MESSAGES:END:(\d+)\}\}"
	return re.sub(pattern, replacement, template)


def replace_prompt_variable(template: str, prompt: str) -> str:
	return template.replace("{{prompt}}", prompt)


def apply_prompt_template(template: str) -> str:
	now = datetime.now()
	template = template.replace("{{CURRENT_DATE}}", now.strftime("%Y-%m-%d"))
	template = template.replace("{{CURRENT_TIME}}", now.strftime("%I:%M:%S %p"))
	template = template.replace(
		"{{CURRENT_DATETIME}}",
		now.strftime("%Y-%m-%d %I:%M:%S %p"),
	)
	template = template.replace("{{CURRENT_WEEKDAY}}", now.strftime("%A"))
	return template


def _build_task_prompt(
	template: str,
	messages: list[dict[str, Any]],
	*,
	prompt: str = "",
	task_type: str = "",
) -> str:
	tmpl = replace_prompt_variable(template, prompt)
	tmpl = replace_messages_variable(tmpl, messages)
	tmpl = tmpl.replace("{{TYPE}}", task_type)
	return apply_prompt_template(tmpl)


def build_title_prompt(
	messages: list[dict[str, Any]],
	template: str | None = None,
) -> str:
	return _build_task_prompt(template or DEFAULT_TITLE_PROMPT_TEMPLATE, messages)


def build_tags_prompt(
	messages: list[dict[str, Any]],
	template: str | None = None,
) -> str:
	return _build_task_prompt(template or DEFAULT_TAGS_PROMPT_TEMPLATE, messages)


def build_follow_up_prompt(
	messages: list[dict[str, Any]],
	template: str | None = None,
) -> str:
	return _build_task_prompt(template or DEFAULT_FOLLOW_UP_PROMPT_TEMPLATE, messages)


def build_autocomplete_prompt(
	messages: list[dict[str, Any]],
	*,
	prompt: str,
	task_type: str = "",
	template: str | None = None,
) -> str:
	return _build_task_prompt(
		template or DEFAULT_AUTOCOMPLETE_PROMPT_TEMPLATE,
		messages,
		prompt=prompt,
		task_type=task_type,
	)


def build_task_prompt(
	task_kind: str,
	messages: list[dict[str, Any]],
	metadata: dict[str, Any],
) -> str | None:
	task_body = metadata.get("task_body")
	body = task_body if isinstance(task_body, dict) else {}
	if task_kind == TASK_TITLE_GENERATION:
		return build_title_prompt(messages)
	if task_kind == TASK_TAGS_GENERATION:
		return build_tags_prompt(messages)
	if task_kind == TASK_FOLLOW_UP_GENERATION:
		return build_follow_up_prompt(messages)
	if task_kind == TASK_AUTOCOMPLETE_GENERATION:
		prompt = str(body.get("prompt") or "")
		task_type = str(body.get("type") or "")
		return build_autocomplete_prompt(messages, prompt=prompt, task_type=task_type)
	return None


def heuristic_query_generation(messages: list[dict[str, Any]]) -> str:
	text = ""
	for message in reversed(messages):
		if isinstance(message, dict) and message.get("role") == "user":
			content = message.get("content")
			text = str(content) if content is not None else ""
			break
	queries = [text.strip()] if text.strip() else []
	return json.dumps({"queries": queries}, ensure_ascii=False)


def normalize_task_result(task_kind: str, raw: str) -> str:
	text = (raw or "").strip()
	if task_kind == TASK_TITLE_GENERATION:
		try:
			data = json.loads(text)
			if isinstance(data, dict) and data.get("title"):
				return str(data["title"]).strip()
		except json.JSONDecodeError:
			pass
		return text
	return text
